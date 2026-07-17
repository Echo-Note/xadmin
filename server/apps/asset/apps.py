"""资产管理应用的配置。"""

from django.apps import AppConfig


class AssetConfig(AppConfig):
    """资产管理应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.asset'
    verbose_name = '资产管理'

    def ready(self) -> None:
        """应用就绪时导入信号处理器。"""
        from . import signals  # noqa

        super().ready()
