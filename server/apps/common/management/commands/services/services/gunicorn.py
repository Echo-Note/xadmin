"""Gunicorn ASGI HTTP 服务模块。"""

import sys

from apps.common.startup import CoreTerminal

from ..hands import APPS_DIR, DEBUG, HTTP_HOST, HTTP_PORT
from .base import BaseService

__all__ = ['GunicornService']


class GunicornService(BaseService):
    """Gunicorn ASGI HTTP 服务器服务。"""

    def __init__(self, **kwargs) -> None:
        """初始化 Gunicorn 服务实例。

        Args:
            **kwargs: 必须包含 ``worker_gunicorn`` 键，指定 worker 数量。
        """
        self.worker = kwargs['worker_gunicorn']
        super().__init__(**kwargs)

    @property
    def cmd(self) -> list:
        """返回启动 Gunicorn 的命令列表。"""
        print('\n- Start Gunicorn ASGI HTTP Server')

        log_format = '%(h)s %(t)s %(L)ss "%(r)s" %(s)s %(b)s '
        bind = f'{HTTP_HOST}:{HTTP_PORT}'

        cmd = [
            sys.executable,
            '-m',
            'gunicorn',
            'server.asgi:application',
            '-b',
            bind,
            '-k',
            'uvicorn.workers.UvicornWorker',
            '-w',
            str(self.worker),
            '--max-requests',
            '10240',
            '--max-requests-jitter',
            '2048',
            '--graceful-timeout',
            '30',
            '--access-logformat',
            log_format,
            '--access-logfile',
            '-',
        ]
        if DEBUG:
            cmd.append('--reload')
        return cmd

    @property
    def cwd(self) -> str:
        """返回服务工作目录。"""
        return APPS_DIR

    def start_other(self) -> None:
        """启动 Gunicorn 后的额外操作：启动核心终端心跳线程。"""
        core_terminal = CoreTerminal()
        core_terminal.start_heartbeat_thread()
