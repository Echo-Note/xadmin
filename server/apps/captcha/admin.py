# Register your models here.
from django.contrib import admin

from apps.captcha.models import CaptchaStore

admin.register(CaptchaStore)
