"""时区与时间相关工具模块。"""

from datetime import datetime

from django.utils import timezone as dj_timezone


def as_current_tz(dt: datetime) -> datetime:
    """将时间转换为当前时区时间。

    Args:
        dt: 待转换的时间对象。

    Returns:
        转换为当前时区后的时间对象。
    """
    return dt.astimezone(dj_timezone.get_current_timezone())


def utc_now() -> datetime:
    """获取当前 UTC 时间。"""
    return dj_timezone.now()


def local_now() -> datetime:
    """获取当前时区的本地时间。"""
    return dj_timezone.localtime(dj_timezone.now())


def local_now_display(fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """获取当前本地时间的格式化字符串。

    Args:
        fmt: 时间格式字符串。

    Returns:
        格式化后的时间字符串。
    """
    return local_now().strftime(fmt)


def local_now_filename() -> str:
    """获取用于文件名的当前本地时间字符串。"""
    return local_now().strftime('%Y%m%d-%H%M%S')


def local_now_date_display(fmt: str = '%Y-%m-%d') -> str:
    """获取当前本地日期的格式化字符串。

    Args:
        fmt: 日期格式字符串。

    Returns:
        格式化后的日期字符串。
    """
    return local_now().strftime(fmt)


def local_zero_hour(fmt: str = '%Y-%m-%d') -> datetime:
    """获取当前本地日期的零点时间对象。

    Args:
        fmt: 日期格式字符串。

    Returns:
        零点对应的 datetime 对象。
    """
    return datetime.strptime(local_now().strftime(fmt), fmt)
