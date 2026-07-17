"""资产管理定时任务。

包含：
- daily_icp_precheck_task：每日凌晨批量执行 ICP 备案悬挂预检测。
- batch_icp_precheck_task：手动触发批量预检测（并发控制，避免带宽暴增）。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from celery import shared_task
from django.db.models import QuerySet

from apps.asset.choices import IcpCheckStatusChoices, IcpFilingStatusChoices
from apps.asset.filing_checker import run_icp_precheck
from apps.asset.models import Filing
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
    now = timezone.now()

    result = run_icp_precheck(domain_name)

    # 回写检测元信息
    filing.icp_has_www_record = result['has_www_record']
    filing.icp_check_status = result['check_status']
    filing.icp_check_conclusion = result['conclusion']
    filing.icp_check_time = now
    if result.get('footer_content') is not None:
        filing.icp_footer_content = result['footer_content']

    # 联动回写 ICP 备案号和状态
    icp_nums = result.get('detected_icp_numbers', [])
    if icp_nums:
        filing.icp_number = icp_nums[0]
        filing.icp_status = IcpFilingStatusChoices.FILED
    elif result['check_status'] == IcpCheckStatusChoices.SUSPECTED_MISSING:
        filing.icp_status = IcpFilingStatusChoices.PENDING_CONFIRM

    # 联动回写公安备案号和状态
    ps_nums = result.get('detected_ps_numbers', [])
    if ps_nums:
        filing.ps_filing_number = ps_nums[0]
        filing.ps_status = IcpFilingStatusChoices.FILED
    elif result['check_status'] == IcpCheckStatusChoices.SUSPECTED_MISSING:
        filing.ps_status = IcpFilingStatusChoices.PENDING_CONFIRM

    filing.save(
        update_fields=[
            'icp_has_www_record',
            'icp_check_status',
            'icp_check_conclusion',
            'icp_check_time',
            'icp_footer_content',
            'icp_number',
            'icp_status',
            'ps_filing_number',
            'ps_status',
        ]
    )

    # 同步更新 Domain 的 SSL 启用状态
    if result.get('has_www_record'):
        filing.domain.is_ssl_enabled = result.get('used_https', False)
        filing.domain.save(update_fields=['is_ssl_enabled'])

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
