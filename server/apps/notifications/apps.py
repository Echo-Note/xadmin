"""通知应用配置。"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NotificationsConfig(AppConfig):
    """通知应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = _('App Notifications')

    def ready(self) -> None:
        """应用就绪时加载后端、信号处理器及消息模块。"""
        from apps.notifications.backends import BACKEND  # noqa
        from . import signal_handlers  # noqa
        from . import notifications  # noqa
        super().ready()
