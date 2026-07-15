"""资产管理应用的配置。"""

from django.apps import AppConfig


class AssetConfig(AppConfig):
    """资产管理应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.asset'
    verbose_name = '资产管理'
