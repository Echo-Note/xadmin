"""消息应用的配置。"""
from django.apps import AppConfig


class MessageConfig(AppConfig):
    """消息应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.message'
