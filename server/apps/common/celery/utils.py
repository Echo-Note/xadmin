#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin_server
# filename : utils
# author : ly_13
# date : 6/29/2023
"""Celery 定时任务与日志工具函数。"""
import json
import os
from datetime import datetime, timedelta, UTC

from django.conf import settings
from django.db.utils import ProgrammingError, OperationalError
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule, CrontabSchedule, PeriodicTask, PeriodicTasks

from apps.common.utils import get_logger
from apps.common.utils.timezone import local_now

logger = get_logger(__name__)

# celery 日志完成之后，写入的魔法字符，作为结束标记
CELERY_LOG_MAGIC_MARK = b'\x00\x00\x00\x00\x00'


def make_dirs(name: str, mode: int = 0o755, exist_ok: bool = False) -> None:
    """创建目录，默认权限设置为 0o755。

    Args:
        name: 目录路径。
        mode: 目录权限。
        exist_ok: 目录已存在时是否不报错。
    """
    os.makedirs(name, mode=mode, exist_ok=exist_ok)


def get_task_log_path(base_path: str, task_id: str, level: int = 0) -> str:
    """根据任务 ID 生成日志文件路径。

    Args:
        base_path: 日志根目录。
        task_id: 任务 ID。
        level: 路径层级，按任务 ID 前缀字符分目录。

    Returns:
        日志文件完整路径。
    """
    task_id = str(task_id)
    rel_path = os.path.join(*task_id[:level], task_id + '.log')
    path = os.path.join(base_path, rel_path)
    make_dirs(os.path.dirname(path), exist_ok=True)
    return path


def get_celery_task_log_path(task_id: str) -> str:
    """获取 Celery 任务日志文件路径。

    Args:
        task_id: 任务 ID。

    Returns:
        日志文件完整路径。
    """
    return get_task_log_path(settings.CELERY_LOG_DIR, task_id)


def eta_second(second: int) -> datetime:
    """计算距当前时间指定秒数后的时间点。

    Args:
        second: 延迟秒数。

    Returns:
        延迟后的 UTC 时间。
    """
    return datetime.fromtimestamp(datetime.now().timestamp(), UTC) + timedelta(seconds=second)


def create_or_update_celery_periodic_tasks(tasks: dict) -> PeriodicTask | None:
    """创建或更新 Celery 定时任务。

    Args:
        tasks: 定时任务配置字典，结构示例如下：

            {
                'add-every-monday-morning': {
                    'task': 'tasks.add',  # 已注册的 celery 任务
                    'interval': 30,
                    'crontab': '30 7 * * *',
                    'args': (16, 16),
                    'kwargs': {},
                    'enabled': False,
                    'description': ''
                },
            }

    Returns:
        创建或更新后的 PeriodicTask 对象，数据库未就绪时返回 None。
    """
    # Todo: check task valid, task and callback must be a celery task
    for name, detail in tasks.items():
        interval = None
        crontab = None
        last_run_at = None

        try:
            IntervalSchedule.objects.all().count()
        except (ProgrammingError, OperationalError):
            return None

        if isinstance(detail.get("interval"), int):
            kwargs = dict(
                every=detail['interval'],
                period=IntervalSchedule.SECONDS,
            )
            # 不能使用 get_or_create，因为可能会有多个
            interval = IntervalSchedule.objects.filter(**kwargs).first()
            if interval is None:
                interval = IntervalSchedule.objects.create(**kwargs)
            last_run_at = local_now()
        elif isinstance(detail.get("crontab"), str):
            try:
                minute, hour, day, month, week = detail["crontab"].split()
            except ValueError:
                logger.error("crontab is not valid")
                return None
            kwargs = dict(
                minute=minute, hour=hour, day_of_week=week,
                day_of_month=day, month_of_year=month, timezone=timezone.get_current_timezone()
            )
            crontab = CrontabSchedule.objects.filter(**kwargs).first()
            if crontab is None:
                crontab = CrontabSchedule.objects.create(**kwargs)
        else:
            logger.error("Schedule is not valid")
            return None

        defaults = dict(
            interval=interval,
            crontab=crontab,
            name=name,
            task=detail['task'],
            args=json.dumps(detail.get('args', [])),
            kwargs=json.dumps(detail.get('kwargs', {})),
            description=detail.get('description') or '',
            last_run_at=last_run_at,
        )
        enabled = detail.get('enabled')
        if enabled is not None:
            defaults["enabled"] = enabled
        task = PeriodicTask.objects.update_or_create(
            defaults=defaults, name=name,
        )
        PeriodicTasks.update_changed()
        return task


def disable_celery_periodic_task(task_name: str) -> None:
    """禁用指定的 Celery 定时任务。

    Args:
        task_name: 定时任务名称。
    """
    from django_celery_beat.models import PeriodicTask
    PeriodicTask.objects.filter(name=task_name).update(enabled=False)
    PeriodicTasks.update_changed()


def delete_celery_periodic_task(task_name: str) -> None:
    """删除指定的 Celery 定时任务。

    Args:
        task_name: 定时任务名称。
    """
    from django_celery_beat.models import PeriodicTask
    PeriodicTask.objects.filter(name=task_name).delete()
    PeriodicTasks.update_changed()


def get_celery_periodic_task(task_name: str) -> PeriodicTask | None:
    """获取指定的 Celery 定时任务对象。

    Args:
        task_name: 定时任务名称。

    Returns:
        PeriodicTask 对象，不存在时返回 None。
    """
    from django_celery_beat.models import PeriodicTask
    task = PeriodicTask.objects.filter(name=task_name).first()
    return task
