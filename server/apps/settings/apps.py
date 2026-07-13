"""设置应用配置。"""

from django.apps import AppConfig


class SettingsConfig(AppConfig):
    """设置应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.settings'

    def ready(self) -> None:
        """应用就绪时加载信号处理器。"""
        from . import signal_handlers  # noqa
        super().ready()
