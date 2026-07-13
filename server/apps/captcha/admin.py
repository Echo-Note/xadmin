"""验证码模型的后台管理配置。"""
# Register your models here.
from django.contrib import admin

from apps.captcha.models import CaptchaStore

admin.register(CaptchaStore)
