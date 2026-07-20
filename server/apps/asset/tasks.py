"""资产管理定时任务。

包含：
- daily_icp_precheck_task：每日凌晨 2:00 批量执行 ICP 备案悬挂预检测。
- daily_ssl_certificate_check_task：每日凌晨 3:00 批量检测 SSL 证书状态。
- batch_icp_precheck_task：手动触发批量预检测（并发控制，避免带宽暴增）。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from celery import shared_task
from django.db.models import QuerySet
from django.utils import timezone

from apps.asset.choices import IcpCheckStatusChoices
from apps.asset.filing_checker import (
    _check_ssl_certificate,
    _sync_ssl_certificate_record,
    apply_precheck_result,
    run_icp_precheck,
)
from apps.asset.models import Domain, Filing
from apps.common.celery.decorator import register_as_period_task
from apps.common.utils import get_logger

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

    # 同步更新 Domain（SSL 启用状态 + 到期时间）
    if result.get('has_www_record'):
        domain_fields = ['is_ssl_enabled']
        if result.get('ssl_certificate'):
            domain_fields.append('ssl_expire_time')
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
    name='asset.icp_precheck.batch',
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

    直接通过 TLS 连接获取证书信息，不依赖备案预检测流程。

    Args:
        domain: Domain 模型实例。

    Returns:
        检测结果摘要字典。

    Raises:
        任意异常向上传播供外层捕获。
    """
    ssl_info = _check_ssl_certificate(domain.domain_name)
    now = timezone.now()

    if ssl_info:
        domain.is_ssl_enabled = True
        domain.ssl_expire_time = ssl_info['not_after'].date()
        _sync_ssl_certificate_record(domain, ssl_info, now)
        domain.save(update_fields=['is_ssl_enabled', 'ssl_expire_time'])
        return {
            'domain_name': domain.domain_name,
            'is_ssl_enabled': True,
            'subject_cn': ssl_info['subject_cn'],
            'not_after': ssl_info['not_after'].strftime('%Y-%m-%d'),
        }
    else:
        domain.is_ssl_enabled = False
        domain.save(update_fields=['is_ssl_enabled'])
        return {
            'domain_name': domain.domain_name,
            'is_ssl_enabled': False,
            'subject_cn': None,
            'not_after': None,
        }


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
