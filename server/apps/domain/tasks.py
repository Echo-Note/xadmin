"""域名管理定时任务。

包含：
- daily_icp_precheck_task：每日凌晨 2:00 批量执行 ICP 备案悬挂预检测。
- daily_ssl_certificate_check_task：每日凌晨 3:00 批量检测 SSL 证书状态。
- batch_icp_precheck_task：手动触发批量预检测（并发控制，避免带宽暴增）。

从 apps.asset.tasks 迁移而来。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from celery import shared_task
from django.db.models import QuerySet
from django.utils import timezone

from apps.common.celery.decorator import register_as_period_task
from apps.common.utils import get_logger
from apps.domain.choices import DnsRecordTypeChoices, IcpCheckStatusChoices
from apps.domain.filing_checker import (
    _check_ssl_certificate,
    _get_name_attr,
    _sync_ssl_certificate_record,
    apply_precheck_result,
    run_icp_precheck,
)
from apps.domain.models import Domain, Filing

logger = get_logger(__name__)

# 需要定时检测的状态：未检测、疑似未悬挂、检测失败
_SHOULD_CHECK_STATUSES = {
    IcpCheckStatusChoices.NOT_CHECKED,
    IcpCheckStatusChoices.SUSPECTED_MISSING,
    IcpCheckStatusChoices.CHECK_FAILED,
}

# 批量检测并发控制
_BATCH_SIZE = 10  # 每批取 10 条
_MAX_WORKERS = 5  # 同时最多 5 个 HTTP 请求
_WORKER_TIMEOUT = 30  # 单个检测超时（秒）


def _run_single_precheck(filing_pk: str) -> dict[str, Any]:
    """对单个 Filing 执行预检测并回写结果。

    Args:
        filing_pk: Filing 主键。

    Returns:
        dict，包含 pk、domain_name、check_status、conclusion。

    Raises:
        任意异常向上传播供外层捕获。
    """
    from django.utils import timezone

    filing = Filing.objects.select_related('domain').get(pk=filing_pk)
    domain_name = filing.domain.domain_name

    result = run_icp_precheck(domain_name)

    # 回写检测结果（公共方法统一处理元信息 + ICP/公安状态联动 + SSL 同步）
    update_fields = apply_precheck_result(filing, result, check_time=timezone.now())
    filing.save(update_fields=update_fields)

    # 同步更新 Domain（SSL 启用状态 + 到期时间 + 证书关联）
    if result.get('has_www_record'):
        domain_fields = ['is_ssl_enabled']
        if result.get('ssl_certificate'):
            domain_fields.extend(['ssl_expire_time', 'ssl_certificate'])
        filing.domain.save(update_fields=domain_fields)

    return {
        'pk': str(filing.pk),
        'domain_name': domain_name,
        'check_status': result['check_status'],
        'conclusion': result['conclusion'],
    }


def _get_applicable_filings(pks: list[str] | None = None) -> QuerySet:
    """获取本次预检测适用的 Filing 查询集。

    Args:
        pks: 指定 PK 列表；为 None 时自动筛选需检测状态。

    Returns:
        Filing 查询集（已预加载 domain）。
    """
    base_qs = Filing.objects.select_related('domain')
    if pks is not None:
        return base_qs.filter(pk__in=pks)
    return base_qs.filter(icp_check_status__in=_SHOULD_CHECK_STATUSES)


def _run_batch_precheck(pks: list[str] | None = None) -> dict[str, Any]:
    """批量预检测公共逻辑，供定时任务和手动触发共用。

    使用 ThreadPoolExecutor 限制最大并发数，避免大量域名同时检测
    导致网络带宽暴增。每批取 _BATCH_SIZE 条，每批内最多 _MAX_WORKERS
    个并发请求，批次间串行执行。

    Args:
        pks: 指定 Filing PK 列表；为 None 时自动筛选。

    Returns:
        汇总结果字典。
    """
    filings = _get_applicable_filings(pks)
    filing_list = list(filings)

    total = len(filing_list)
    if total == 0:
        logger.info('无待检测的备案记录，跳过批量预检测')
        return {'total': 0, 'checked': 0, 'errors': 0, 'details': []}

    logger.info('批量预检测开始：共 %d 条（批次大小=%d, 并发数=%d）', total, _BATCH_SIZE, _MAX_WORKERS)

    checked = 0
    errors = 0
    details: list[dict[str, Any]] = []

    for start in range(0, total, _BATCH_SIZE):
        chunk = filing_list[start : start + _BATCH_SIZE]
        chunk_pks = [str(f.pk) for f in chunk]

        logger.debug('批次 %d/%d: %d 条', start // _BATCH_SIZE + 1, (total - 1) // _BATCH_SIZE + 1, len(chunk))

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {executor.submit(_run_single_precheck, pk): pk for pk in chunk_pks}
            for future in as_completed(futures, timeout=_WORKER_TIMEOUT * _MAX_WORKERS):
                pk = futures[future]
                try:
                    result = future.result(timeout=_WORKER_TIMEOUT)
                    checked += 1
                    details.append(result)
                    logger.info('预检测完成 [%s]: %s', result['domain_name'], result['check_status'])
                except Exception as e:
                    errors += 1
                    details.append(
                        {
                            'pk': pk,
                            'domain_name': '未知',
                            'check_status': IcpCheckStatusChoices.CHECK_FAILED,
                            'conclusion': f'检测异常: {e}',
                        }
                    )
                    logger.exception('预检测异常 [pk=%s]', pk)

    logger.info('批量预检测结束：共 %d 条，成功 %d 条，失败 %d 条', total, checked, errors)

    return {
        'total': total,
        'checked': checked,
        'errors': errors,
        'details': details,
    }


# =============================================================================
# 手动触发批量预检测任务
# =============================================================================


@shared_task(
    name='domain.icp_precheck.batch',
    verbose_name='批量 ICP 备案预检测',
)
def batch_icp_precheck_task(pks: list[str] | None = None) -> dict[str, Any]:
    """手动触发批量 ICP 备案预检测（异步执行）。

    由 API 触发，通过 ThreadPoolExecutor 控制并发（最多 5 个同时请求），
    批次间串行，避免网络带宽暴增。

    Args:
        pks: 指定 Filing PK 列表。为 None 时自动筛选需检测的记录。

    Returns:
        汇总结果字典。
    """
    return _run_batch_precheck(pks)


# =============================================================================
# 每日定时预检测任务
# =============================================================================


@shared_task(verbose_name='每日 ICP 备案预检测')
@register_as_period_task(
    crontab='0 2 * * *',
    description='每天凌晨 2:00 自动检测域名首页页脚是否悬挂 ICP 备案号',
)
def daily_icp_precheck_task() -> dict:
    """每日定时 ICP 备案预检测（凌晨 2:00）。

    复用 _run_batch_precheck 实现并发控制，自动筛选需检测的记录。
    """
    return _run_batch_precheck()


# =============================================================================
# SSL 证书定时检测
# =============================================================================


def _check_single_ssl(domain: Domain) -> dict[str, Any]:
    """检测单个域名的 SSL 证书并更新记录。

    检测流程：
    1. 检测主域名 www.{domain_name} 的 SSL 证书
    2. 查询该域名的 DNS 解析记录中的 A/AAAA 子域名，逐个检测 SSL
    3. 相同证书（指纹去重）共用一条 SslCertificate 记录
    4. 子域名在 Domain 表中有独立记录时更新其 ssl_certificate 关联

    Args:
        domain: Domain 模型实例。

    Returns:
        检测结果摘要字典。

    Raises:
        任意异常向上传播供外层捕获。
    """
    from apps.domain.models import DnsRecord

    ssl_info = _check_ssl_certificate(domain.domain_name)
    now = timezone.now()

    if ssl_info:
        domain.is_ssl_enabled = True
        domain.ssl_expire_time = ssl_info['not_after'].date()
        _sync_ssl_certificate_record(domain, ssl_info, now)
        domain.save(update_fields=['is_ssl_enabled', 'ssl_expire_time', 'ssl_certificate'])
        main_result = {
            'domain_name': domain.domain_name,
            'is_ssl_enabled': True,
            'subject_cn': ssl_info['subject_cn'],
            'not_after': ssl_info['not_after'].strftime('%Y-%m-%d'),
        }
    else:
        domain.is_ssl_enabled = False
        domain.ssl_certificate = None
        domain.save(update_fields=['is_ssl_enabled', 'ssl_certificate'])
        main_result = {
            'domain_name': domain.domain_name,
            'is_ssl_enabled': False,
            'subject_cn': None,
            'not_after': None,
        }

    # 检测二级域名（DNS A/AAAA 记录指向的子域名）
    sub_results: list[dict[str, Any]] = []
    dns_records = DnsRecord.objects.filter(
        domain=domain,
        record_type__in=[DnsRecordTypeChoices.A, DnsRecordTypeChoices.AAAA],
    ).exclude(host__in=['@', 'www', ''])  # 主域名和 www 已检测过

    for record in dns_records:
        sub_domain_name = f'{record.host}.{domain.domain_name}'
        sub_ssl_info = _check_ssl_certificate_by_host(sub_domain_name)

        # 更新 DnsRecord 的 SSL 状态
        record.is_ssl_enabled = sub_ssl_info is not None
        record.save(update_fields=['is_ssl_enabled'])

        if not sub_ssl_info:
            continue

        # 查找子域名是否有独立的 Domain 记录
        sub_domain = Domain.objects.filter(domain_name=sub_domain_name, is_active=True).first()
        if sub_domain:
            sub_domain.is_ssl_enabled = True
            sub_domain.ssl_expire_time = sub_ssl_info['not_after'].date()
            _sync_ssl_certificate_record(sub_domain, sub_ssl_info, now)
            sub_domain.save(update_fields=['is_ssl_enabled', 'ssl_expire_time', 'ssl_certificate'])
            sub_results.append(
                {
                    'domain_name': sub_domain_name,
                    'is_ssl_enabled': True,
                    'subject_cn': sub_ssl_info['subject_cn'],
                    'same_as_main': sub_ssl_info['fingerprint'] == ssl_info.get('fingerprint') if ssl_info else False,
                }
            )

    main_result['subdomains'] = sub_results
    return main_result


def _check_ssl_certificate_by_host(hostname: str) -> dict[str, Any] | None:
    """检测指定主机名的 SSL 证书（复用 _check_ssl_certificate 逻辑）。

    与 _check_ssl_certificate 的区别：直接用完整主机名连接，不加 www 前缀。

    Args:
        hostname: 完整主机名，如 mail.example.com。

    Returns:
        证书信息字典，失败返回 None。
    """
    import socket
    import ssl as ssl_module

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import ExtensionOID, NameOID

    try:
        ctx = ssl_module.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)

                # 获取完整证书链
                der_chain: list[bytes] | None = None
                get_chain = getattr(ssock, 'get_unverified_chain', None)
                if get_chain is None:
                    get_chain = getattr(getattr(ssock, '_sslobj', None), 'get_unverified_chain', None)
                if get_chain is not None:
                    try:
                        der_chain = list(get_chain())
                    except Exception:
                        der_chain = None

        if not der_cert:
            return None

        cert = x509.load_der_x509_certificate(der_cert)

        # PEM 格式证书
        certificate_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        intermediate_pem = ''
        if der_chain and len(der_chain) > 1:
            parts: list[str] = []
            for der_bytes in der_chain[1:]:
                try:
                    chain_cert = x509.load_der_x509_certificate(der_bytes)
                    parts.append(chain_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8'))
                except Exception:
                    pass
            intermediate_pem = ''.join(parts)

        subject = cert.subject
        issuer = cert.issuer
        subject_cn = _get_name_attr(subject, NameOID.COMMON_NAME)
        issuer_cn = _get_name_attr(issuer, NameOID.COMMON_NAME)
        issuer_o = _get_name_attr(issuer, NameOID.ORGANIZATION_NAME)

        san_domains: list[str] = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_domains = san_ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            pass

        not_before = getattr(cert, 'not_valid_before_utc', None) or cert.not_valid_before
        not_after = getattr(cert, 'not_valid_after_utc', None) or cert.not_valid_after

        from datetime import UTC, datetime

        now_utc = datetime.now(UTC)
        is_valid = not_before <= now_utc <= not_after

        sig_algo = cert.signature_hash_algorithm
        return {
            'subject_cn': subject_cn,
            'subject_o': _get_name_attr(subject, NameOID.ORGANIZATION_NAME),
            'subject_ou': _get_name_attr(subject, NameOID.ORGANIZATIONAL_UNIT_NAME),
            'issuer_cn': issuer_cn,
            'issuer_o': issuer_o,
            'serial_number': format(cert.serial_number, 'x'),
            'signature_algorithm': sig_algo.name if sig_algo else None,
            'not_before': not_before,
            'not_after': not_after,
            'san_domains': san_domains,
            'is_valid': is_valid,
            'fingerprint': cert.fingerprint(hashes.SHA256()).hex(),
            'certificate_pem': certificate_pem,
            'intermediate_pem': intermediate_pem,
        }
    except (ssl_module.SSLError, OSError):
        return None
    except Exception as e:
        logger.debug('SSL 证书检测失败 %s: %s', hostname, e)
        return None


def _run_batch_ssl_check() -> dict[str, Any]:
    """批量 SSL 证书检测，复用并发控制逻辑。

    只检测已开启 SSL 的域名（is_ssl_enabled=True），避免对无 SSL 的域名
    做无意义的 TLS 连接尝试。通过 ThreadPoolExecutor 控制并发
    （最多 _MAX_WORKERS 个同时请求），避免带宽暴增。

    Returns:
        汇总结果字典。
    """
    domains = list(Domain.objects.filter(is_active=True, is_ssl_enabled=True))
    total = len(domains)

    if total == 0:
        logger.info('无待检测的域名，跳过 SSL 证书检测')
        return {'total': 0, 'checked': 0, 'errors': 0}

    logger.info(
        '批量 SSL 证书检测开始：共 %d 个域名（批次=%d, 并发=%d）',
        total,
        _BATCH_SIZE,
        _MAX_WORKERS,
    )

    checked = 0
    errors = 0

    for start in range(0, total, _BATCH_SIZE):
        chunk = domains[start : start + _BATCH_SIZE]

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {executor.submit(_check_single_ssl, d): d for d in chunk}
            for future in as_completed(futures, timeout=_WORKER_TIMEOUT * _MAX_WORKERS):
                domain = futures[future]
                try:
                    result = future.result(timeout=_WORKER_TIMEOUT)
                    checked += 1
                    logger.debug(
                        'SSL 检测完成 [%s]: enabled=%s',
                        result['domain_name'],
                        result['is_ssl_enabled'],
                    )
                except Exception as e:
                    errors += 1
                    logger.exception('SSL 检测异常 [%s]: %s', domain.domain_name, e)

    logger.info(
        '批量 SSL 证书检测结束：共 %d 个，成功 %d，失败 %d',
        total,
        checked,
        errors,
    )

    return {'total': total, 'checked': checked, 'errors': errors}


@shared_task(verbose_name='每日 SSL 证书检测')
@register_as_period_task(
    crontab='0 3 * * *',
    description='每天凌晨 3:00 自动检测所有域名的 SSL 证书状态',
)
def daily_ssl_certificate_check_task() -> dict[str, Any]:
    """每日定时 SSL 证书检测（凌晨 3:00）。

    错开备案预检测（02:00），遍历所有启用域名检测 SSL 证书详情，
    更新 SslCertificate 记录及 Domain 的 is_ssl_enabled / ssl_expire_time。
    """
    return _run_batch_ssl_check()
