"""Celery Beat 定时任务调度服务模块。"""

from ..hands import *
from .base import BaseService

__all__ = ['BeatService']


class BeatService(BaseService):
    """Celery Beat 定时任务调度器服务。"""

    def __init__(self, **kwargs) -> None:
        """初始化 Beat 服务实例。"""
        super().__init__(**kwargs)

    @property
    def cmd(self) -> list:
        """返回启动 Beat 调度器的命令列表。"""
        scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'
        print('\n- Start Beat as Periodic Task Scheduler')
        cmd = [
            sys.executable,
            '-m',
            'celery',
            '-A',
            'server',
            'beat',
            '-l',
            'INFO',
            '--scheduler',
            scheduler,
            '--max-interval',
            '60',
        ]
        return cmd

    @property
    def cwd(self) -> str:
        """返回服务工作目录。"""
        return APPS_DIR
