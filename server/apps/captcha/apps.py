"""验证码应用的配置。"""
from django.apps import AppConfig


class CaptchaConfig(AppConfig):
    """验证码应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.captcha'
