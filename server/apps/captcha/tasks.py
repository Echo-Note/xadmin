"""验证码定时任务。"""
from celery import shared_task

from apps.captcha.models import CaptchaStore
from apps.common.celery.decorator import register_as_period_task


@shared_task
@register_as_period_task(crontab='12 2 * * *')
def auto_clean_expired_captcha_job() -> None:
    """定时清理过期的验证码记录。"""
    CaptchaStore.remove_expired()
