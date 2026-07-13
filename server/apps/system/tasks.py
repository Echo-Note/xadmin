"""系统应用定时任务。"""

from celery import shared_task

from apps.common.celery.decorator import register_as_period_task
from apps.common.utils import get_logger
from apps.system.utils.ctasks import auto_clean_operation_log, auto_clean_black_token, auto_clean_tmp_file

logger = get_logger(__name__)


@shared_task
@register_as_period_task(crontab='2 2 * * *')
def auto_clean_operation_job() -> None:
    """定时清理过期操作日志。"""
    auto_clean_operation_log(clean_day=30 * 6)


@shared_task
@register_as_period_task(crontab='22 2 * * *')
def auto_clean_black_token_job() -> None:
    """定时清理过期黑名单令牌。"""
    auto_clean_black_token(clean_day=7)


@shared_task
@register_as_period_task(crontab='32 2 * * *')
def auto_clean_tmp_file_job() -> None:
    """定时清理临时上传文件。"""
    auto_clean_tmp_file(clean_day=7)
