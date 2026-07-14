"""云平台管理应用的配置。"""

from django.apps import AppConfig


class CloudPlatformConfig(AppConfig):
    """云平台管理应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cloud_platform'
    verbose_name = '云平台管理'
