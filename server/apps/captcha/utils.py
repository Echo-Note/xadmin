"""验证码认证工具类。"""
#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : util
# author : ly_13
# date : 8/10/2024

from django.http import HttpRequest
from django.utils import timezone

from apps.captcha.helpers import captcha_image_url
from apps.captcha.models import CaptchaStore
from apps.common.utils import get_logger

logger = get_logger(__name__)


class CaptchaAuth:
    """验证码认证类，提供验证码生成与校验功能。"""

    def __init__(self, captcha_key: str = '', request: HttpRequest = None) -> None:
        """初始化验证码认证实例。

        Args:
            captcha_key: 验证码 hashkey。
            request: HTTP 请求对象，用于构建绝对 URI。
        """
        self.captcha_key = captcha_key
        self.request = request

    def __get_captcha_obj(self) -> CaptchaStore | None:
        """根据 hashkey 获取验证码存储对象。"""
        return CaptchaStore.objects.filter(hashkey=self.captcha_key).first()

    def generate(self) -> dict:
        """生成新的验证码并返回图片地址等信息。

        Returns:
            包含 captcha_image、captcha_key 和 length 的字典。
        """
        self.captcha_key = CaptchaStore.generate_key()
        captcha_image = captcha_image_url(self.captcha_key)
        if self.request:
            captcha_image = self.request.build_absolute_uri(captcha_image)
        captcha_obj = self.__get_captcha_obj()
        code_length = 0
        if captcha_obj:
            code_length = len(captcha_obj.response)
        return {"captcha_image": captcha_image, "captcha_key": self.captcha_key, "length": code_length}

    def valid(self, verify_code: str) -> bool:
        """校验用户输入的验证码是否正确。

        Args:
            verify_code: 用户输入的验证码。

        Returns:
            校验通过返回 True，否则返回 False。
        """
        try:
            CaptchaStore.objects.get(
                response=verify_code.strip(" ").lower(), hashkey=self.captcha_key, expiration__gt=timezone.now()
            ).delete()
        except CaptchaStore.DoesNotExist:
            return False
        return True
