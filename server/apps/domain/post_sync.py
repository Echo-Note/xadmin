"""域名同步后处理 — SSL 证书检测 + 备案信息联动。

在域名 + DNS 记录同步完成后执行，作为同步流程的 Phase 3：

流程：
1. 遍历当前平台的所有域名
2. 检测每个域名是否存在 www 解析记录（两级检测）：
   a. 快速路径：查询 DnsRecord 表是否有 host='www' 的记录
   b. 慢速路径：对表中无 www 记录的域名，通过 HTTP/HTTPS 请求检测
      → 覆盖「域名在 A 平台、DNS 托管在 B 平台」的场景
3. 有 www 记录的域名：
   a. 创建 Filing 备案记录（如不存在）
   b. 检测 www.{domain}:443 的 SSL 证书
   c. SSL 可用时：创建 SslCertificate 记录，更新 Domain SSL 字段
4. 无 www 记录的域名：删除已有的 Filing 记录（备案信息不应存在）

设计要点：
- Filing 的存在与否完全由 www 记录决定，不通过信号自动创建
- www 检测的两级策略确保 DNS 跨平台托管的域名也能被正确识别
- HTTP fallback 通过实际请求检测，不受 VPN 通配 DNS 影响
  （只有获得实际 HTTP 响应才判定 www 存在；SSLError/超时不算，
  因为 VPN 代理可能对所有 www 子域名通配开放 443 端口但 TLS 握手失败）
- ICP 预检测通过 Celery 异步派发（batch_icp_precheck_task.delay），
  不阻塞同步流程；任务内部有批次控制（10条/批，5并发）
- SSL 检测使用 ThreadPoolExecutor 并行执行，避免串行等待
- ICP 备案号预检测（页脚抓取）不在同步流程中执行，由独立的定时任务/手动触发完成
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

import requests
from django.utils import timezone

from apps.domain.choices import IcpCheckStatusChoices, IcpFilingStatusChoices
from apps.domain.filing_checker import _check_ssl_certificate

if TYPE_CHECKING:
    from apps.cloud_platform.models import CloudPlatform

logger = logging.getLogger(__name__)

# www 检测 / SSL 检测并发控制
_MAX_WORKERS = 5
# HTTP 请求超时（秒）
_HTTP_TIMEOUT = 10
# SSL 检测超时（秒），由 _check_ssl_certificate 内部 HTTP_TIMEOUT 控制
_SSL_TIMEOUT = 30


def process_domains_post_sync(platform: CloudPlatform) -> dict[str, Any]:
    """域名同步后处理：根据 www 记录联动 Filing 备案 + SSL 证书检测。

    www 检测两级策略：
    1. 快速路径：DnsRecord 表中是否有 host='www' 记录
    2. 慢速路径：HTTP/HTTPS 请求 www.{domain} 检测是否可访问
       → 覆盖 DNS 托管在其他平台的域名（DnsRecord 表无记录但实际有 www）

    Args:
        platform: 当前同步的云平台实例。

    Returns:
        处理结果统计字典。
    """
    from apps.domain.models import DnsRecord, Domain, Filing

    stats: dict[str, Any] = {
        'filings_created': 0,
        'filings_removed': 0,
        'ssl_checked': 0,
        'ssl_enabled': 0,
        'ssl_certificates_created': 0,
        'www_detected_by_db': 0,
        'www_detected_by_http': 0,
        'precheck_total': 0,
        'precheck_dispatched': False,
        'precheck_task_id': None,
        'errors': [],
    }

    domains = list(Domain.objects.filter(platform=platform, is_active=True))
    if not domains:
        logger.info('平台 [%s] 无活跃域名，跳过后处理', platform.name)
        return stats

    logger.info('开始域名后处理 [%s]: 共 %d 个域名', platform.name, len(domains))

    # ---- Step 1: 快速路径 — DnsRecord 表查询 www 记录 ----
    www_domain_ids = set(DnsRecord.objects.filter(host='www', domain__in=domains).values_list('domain_id', flat=True))
    domains_with_www_db = [d for d in domains if d.pk in www_domain_ids]
    domains_without_www_db = [d for d in domains if d.pk not in www_domain_ids]
    stats['www_detected_by_db'] = len(domains_with_www_db)

    logger.info(
        '[%s] DnsRecord 表有 www 记录: %d 个，无 www 记录: %d 个（需 HTTP 检测）',
        platform.name,
        len(domains_with_www_db),
        len(domains_without_www_db),
    )

    # ---- Step 2: 慢速路径 — HTTP/HTTPS 检测 www 可访问性 ----
    domains_with_www_http: list = []
    if domains_without_www_db:
        http_results = _batch_check_www_accessible(domains_without_www_db)
        domains_with_www_http = [d for d in domains_without_www_db if http_results.get(d.pk, False)]
        stats['www_detected_by_http'] = len(domains_with_www_http)
        logger.info(
            '[%s] HTTP 检测新增 www 域名: %d 个（共检测 %d 个）',
            platform.name,
            len(domains_with_www_http),
            len(domains_without_www_db),
        )

    # ---- Step 3: 合并 — 有 www / 无 www ----
    domains_with_www = domains_with_www_db + domains_with_www_http
    domains_without_www = [d for d in domains_without_www_db if d not in domains_with_www_http]

    # ---- Step 4: 无 www 的域名 → 删除 Filing ----
    if domains_without_www:
        deleted_count, _ = Filing.objects.filter(domain__in=domains_without_www).delete()
        stats['filings_removed'] = deleted_count

    # ---- Step 5: 有 www 的域名 → 创建 Filing + 检测 SSL ----
    for domain in domains_with_www:
        filing, created = Filing.objects.get_or_create(
            domain=domain,
            defaults={
                'company': domain.company,
                'icp_status': IcpFilingStatusChoices.NOT_FILED,
                'ps_status': IcpFilingStatusChoices.NOT_FILED,
                'icp_has_www_record': True,
                'icp_check_status': IcpCheckStatusChoices.NOT_CHECKED,
            },
        )
        if created:
            stats['filings_created'] += 1
        elif not filing.icp_has_www_record:
            filing.icp_has_www_record = True
            filing.save(update_fields=['icp_has_www_record'])

    logger.info(
        '[%s] 有 www 记录的域名 %d 个，新建 Filing %d 条，开始 ICP 预检测...',
        platform.name,
        len(domains_with_www),
        stats['filings_created'],
    )

    # ---- Step 5.5: 异步派发 ICP 预检测（Celery 队列管理，不阻塞同步）----
    # 创建 Filing 后立即派发预检测任务到 Celery 队列
    # batch_icp_precheck_task 内部有批次控制（10条/批，5并发）
    # Celery worker 异步执行，同步流程不阻塞
    if domains_with_www:
        filing_pks = list(Filing.objects.filter(domain__in=domains_with_www).values_list('pk', flat=True))
        filing_pks = [str(pk) for pk in filing_pks]
        stats['precheck_total'] = len(filing_pks)

        if filing_pks:
            try:
                from apps.domain.tasks import batch_icp_precheck_task

                task = batch_icp_precheck_task.delay(pks=filing_pks)
                stats['precheck_dispatched'] = True
                stats['precheck_task_id'] = task.id
                logger.info(
                    '[%s] ICP 预检测已异步派发: task_id=%s, 待检测=%d 条',
                    platform.name,
                    task.id,
                    len(filing_pks),
                )
            except Exception as e:
                logger.warning(
                    '[%s] ICP 预检测派发失败（Celery 未运行？）: %s',
                    platform.name,
                    e,
                )

    # ---- Step 6: 并行检测 SSL 证书 ----
    # 预检测已做基础 SSL 检测（HTTPS 可达时），此处做更完整检测（含 verify=False 降级）
    if domains_with_www:
        ssl_results = _batch_check_ssl(domains_with_www)
        stats['ssl_checked'] = len(ssl_results)

        for domain, ssl_info in ssl_results.items():
            if ssl_info is None:
                domain.is_ssl_enabled = False
                domain.ssl_certificate = None
                domain.save(update_fields=['is_ssl_enabled', 'ssl_certificate'])
                continue

            stats['ssl_enabled'] += 1
            now = timezone.now()

            from apps.domain.models import SslCertificate

            cert, cert_created = SslCertificate.objects.update_or_create(
                fingerprint=ssl_info['fingerprint'],
                defaults={
                    'subject_cn': ssl_info['subject_cn'],
                    'subject_o': ssl_info['subject_o'],
                    'subject_ou': ssl_info['subject_ou'],
                    'issuer_cn': ssl_info['issuer_cn'],
                    'issuer_o': ssl_info['issuer_o'],
                    'serial_number': ssl_info['serial_number'],
                    'signature_algorithm': ssl_info['signature_algorithm'],
                    'not_before': ssl_info['not_before'],
                    'not_after': ssl_info['not_after'],
                    'san_domains': ssl_info['san_domains'],
                    'is_valid': ssl_info['is_valid'],
                    'check_time': now,
                    'certificate_pem': ssl_info.get('certificate_pem'),
                    'intermediate_pem': ssl_info.get('intermediate_pem'),
                },
            )
            if cert_created:
                stats['ssl_certificates_created'] += 1

            domain.is_ssl_enabled = True
            domain.ssl_expire_time = ssl_info['not_after'].date()
            domain.ssl_certificate = cert
            domain.save(update_fields=['is_ssl_enabled', 'ssl_expire_time', 'ssl_certificate'])

    logger.info(
        '域名后处理完成 [%s]: www(DB=%d,HTTP=%d) Filing新建=%d 删除=%d, '
        'ICP预检测派发=%s(%d条) SSL检测=%d 可用=%d 证书新建=%d',
        platform.name,
        stats['www_detected_by_db'],
        stats['www_detected_by_http'],
        stats['filings_created'],
        stats['filings_removed'],
        '是' if stats['precheck_dispatched'] else '否',
        stats['precheck_total'],
        stats['ssl_checked'],
        stats['ssl_enabled'],
        stats['ssl_certificates_created'],
    )

    return stats


# ======================================================================
# www 可访问性检测（HTTP fallback）
# ======================================================================


def _batch_check_www_accessible(domains: list) -> dict:
    """并行检测多个域名的 www 可访问性。

    用于 DnsRecord 表中没有 www 记录的域名，通过实际 HTTP/HTTPS 请求
    检测 www 是否存在。覆盖 DNS 托管在其他平台的场景。

    Args:
        domains: Domain 实例列表。

    Returns:
        {domain.pk: bool} 字典，True 表示 www 可访问。
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    results: dict = {}

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_check_www_accessible, d.domain_name): d for d in domains}
        for future in as_completed(futures, timeout=_HTTP_TIMEOUT * 2 * len(domains)):
            domain = futures[future]
            try:
                results[domain.pk] = future.result(timeout=_HTTP_TIMEOUT * 2)
            except Exception as e:
                logger.debug('www 可访问性检测异常 [%s]: %s', domain.domain_name, e)
                results[domain.pk] = False

    return results


def _check_www_accessible(domain_name: str) -> bool:
    """通过 HTTP/HTTPS 请求检测 www.{domain} 是否可访问。

    检测策略：
    1. 尝试 HTTPS（verify=False 允许过期/自签名证书）
       - 有响应 → www 存在
       - SSLError → 端口开放但 TLS 握手失败 → www 存在
       - ReadTimeout → 连接已建立但读超时 → www 存在
       - ConnectTimeout/ConnectionError → 端口关闭 → 尝试 HTTP
    2. 尝试 HTTP
       - 有响应 → www 存在
       - 失败 → www 不存在

    通过实际 HTTP 请求检测，不受 VPN 通配 DNS 影响：
    VPN 代理会根据 Host/SNI 转发请求，不存在的子域名会被拒绝（ConnectionError）。

    Args:
        domain_name: 域名（不含 www 前缀）。

    Returns:
        True 表示 www 可访问（www 记录存在）。
    """
    www_host = f'www.{domain_name}'

    # 尝试 HTTPS
    result = _try_request(f'https://{www_host}/', verify=False)
    if result is not False:
        return result

    # 尝试 HTTP
    result = _try_request(f'http://{www_host}/', verify=True)
    return result


def _try_request(url: str, verify: bool = True) -> bool:
    """尝试 HTTP 请求，返回 www 是否存在。

    判定规则：只有获得实际 HTTP 响应（状态码 200/302/403 等）才判定 www 存在。
    SSLError / Timeout / ConnectionError 均不算（可能是 VPN 代理通配行为）。

    Args:
        url: 完整 URL。
        verify: 是否校验 SSL 证书。

    Returns:
        True: 有实际 HTTP 响应（www 存在）
        False: 无响应（www 不存在或需尝试下一方案）
    """
    try:
        requests.get(url, timeout=_HTTP_TIMEOUT, allow_redirects=False, verify=verify)
        return True  # 有实际 HTTP 响应 → www 存在
    except requests.RequestException:
        # SSLError（代理通配端口）/ Timeout / ConnectionError → 不算 www 存在
        return False


# ======================================================================
# SSL 证书检测
# ======================================================================


def _batch_check_ssl(domains: list) -> dict:
    """并行检测多个域名的 SSL 证书。

    Args:
        domains: Domain 实例列表。

    Returns:
        {domain: ssl_info | None} 字典，ssl_info 为 None 表示 SSL 不可用。
    """
    results: dict = {}

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_check_ssl_certificate_safe, d.domain_name): d for d in domains}
        for future in as_completed(futures, timeout=_SSL_TIMEOUT * len(domains)):
            domain = futures[future]
            try:
                ssl_info = future.result(timeout=_SSL_TIMEOUT)
                results[domain] = ssl_info
            except Exception as e:
                logger.warning('SSL 检测异常 [%s]: %s', domain.domain_name, e)
                results[domain] = None

    return results


def _check_ssl_certificate_safe(domain_name: str) -> dict[str, Any] | None:
    """安全包装的 SSL 证书检测，捕获所有异常避免线程池中断。

    Args:
        domain_name: 域名（不含 www 前缀，由 _check_ssl_certificate 自动拼接）。

    Returns:
        证书信息字典，检测失败返回 None。
    """
    try:
        return _check_ssl_certificate(domain_name)
    except Exception as e:
        logger.debug('SSL 检测失败 [%s]: %s', domain_name, e)
        return None
