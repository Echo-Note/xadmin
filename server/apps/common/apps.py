"""common 应用配置。"""
from __future__ import unicode_literals

import sys
import threading
import time

from django.apps import AppConfig


class CommonConfig(AppConfig):
    """common 应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'

    def ready(self) -> None:
        """应用就绪时初始化信号处理器、任务及心跳，并异步发送 django_ready 信号。"""
        from .celery import heatbeat  # noqa
        from . import signal_handlers  # noqa
        from . import tasks  # noqa
        from .signals import django_ready
        excludes = ['migrate', 'compilemessages', 'makemigrations', 'stop']
        for i in excludes:
            if i in sys.argv:
                return
        super().ready()

        def background_task() -> None:
            time.sleep(0.1)
            django_ready.send(CommonConfig)

        threading.Thread(target=background_task, daemon=True).start()

