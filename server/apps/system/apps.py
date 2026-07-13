"""系统应用配置模块。"""

from django.apps import AppConfig


class SystemConfig(AppConfig):
    """系统应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system'

    def ready(self) -> None:
        """应用就绪时导入信号处理器。"""
        from . import signal_handler  # noqa
        super().ready()
