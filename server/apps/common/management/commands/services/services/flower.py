"""Flower 任务监控服务模块。"""

import os
import sys

from django.conf import settings

from ..hands import APPS_DIR, CELERY_FLOWER_AUTH, CELERY_FLOWER_HOST, CELERY_FLOWER_PORT, LOG_DIR
from .base import BaseService

__all__ = ['FlowerService']


class FlowerService(BaseService):
    """Flower Celery 任务监控服务。

    参考: https://flower.readthedocs.io/en/latest/man.html?highlight=pool#description
    """

    def __init__(self, **kwargs) -> None:
        """初始化 Flower 服务实例。"""
        super().__init__(**kwargs)

    @property
    def db_file(self) -> str:
        """返回 Flower 持久化数据库文件路径。"""
        return os.path.join(LOG_DIR, 'flower.db')

    @property
    def cmd(self) -> list:
        """返回启动 Flower 监控的命令列表。"""
        print('\n- Start Flower as Task Monitor')

        if os.getuid() == 0:
            os.environ.setdefault('C_FORCE_ROOT', '1')
        cmd = [
            sys.executable,
            '-m',
            'celery',
            '-A',
            'server',
            'flower',
            '-logging=info',
            '--url_prefix=api/flower',
            '--auto_refresh=False',
            '--max_tasks=1000',
            '--persistent=True',
            '--state_save_interval=600000',
            f'--basic-auth={CELERY_FLOWER_AUTH}',  # 注释则代表 flower 只读权限
            f'-db={self.db_file}',
            '--state_save_interval=600000',
            f'--address={CELERY_FLOWER_HOST}',
            f'--port={CELERY_FLOWER_PORT}',
        ]
        if settings.DEBUG:
            cmd += ['--debug']
        return cmd

    @property
    def cwd(self) -> str:
        """返回服务工作目录。"""
        return APPS_DIR
