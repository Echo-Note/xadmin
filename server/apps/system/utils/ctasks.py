"""系统应用定时任务工具函数。"""

import datetime

from celery.utils.log import get_task_logger
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.system.models import OperationLog, UploadFile

logger = get_task_logger(__name__)


def auto_clean_operation_log(clean_day: int = 30 * 6) -> None:
    """清理过期操作日志。

    Args:
        clean_day: 保留天数，默认 180 天。
    """
    OperationLog.remove_expired(clean_day)


def auto_clean_black_token(clean_day: int = 1) -> None:
    """清理过期的黑名单令牌。

    Args:
        clean_day: 保留天数，默认 1 天。
    """
    clean_time = timezone.now() - datetime.timedelta(days=clean_day)
    deleted, _rows_count = OutstandingToken.objects.filter(expires_at__lte=clean_time).delete()
    logger.info(f"clean {_rows_count} black token {deleted}")


def auto_clean_tmp_file(clean_day: int = 1) -> None:
    """清理临时上传文件。

    Args:
        clean_day: 保留天数，默认 1 天。
    """
    clean_time = timezone.now() - datetime.timedelta(days=clean_day)
    _rows_count = 0
    for instance in UploadFile.objects.filter(created_time__lte=clean_time, is_tmp=True):
        if instance.delete():
            _rows_count += 1
    logger.info(f"clean {_rows_count} upload tmp file")
