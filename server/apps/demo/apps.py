"""演示应用的配置。"""
from django.apps import AppConfig


class DemoConfig(AppConfig):
    """演示应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.demo'
