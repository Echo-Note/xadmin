#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : verify_code
# author : ly_13
# date : 8/6/2024
"""验证码生成、发送与验证工具模块。"""

import time
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.common.sdk.sms.endpoint import SMS
from apps.common.sdk.sms.exceptions import CodeError, CodeExpired, CodeSendOverRate
from apps.common.tasks import send_mail_async
from apps.common.utils import get_logger, random_string

logger = get_logger(__name__)


@shared_task(verbose_name=_('Send SMS code'))
def send_sms_async(target: str, code: str) -> None:
    """异步发送短信验证码。

    Args:
        target: 接收验证码的手机号。
        code: 验证码内容。
    """
    SMS().send_verify_code(target, code)


class SendAndVerifyCodeUtil(object):
    """验证码发送与验证工具类。"""

    KEY_TMPL = 'auth_verify_code_{}'
    RATE_KEY_TMPL = 'auth_verify_code_send_at_{}'

    def __init__(
        self,
        target: str,
        code: str | None = None,
        key: str | None = None,
        backend: str = 'email',
        timeout: int | None = None,
        limit: int | None = None,
        dryrun: bool = False,
        **kwargs: Any,
    ) -> None:
        """初始化验证码工具。

        Args:
            target: 验证码接收目标（邮箱或手机号）。
            code: 指定的验证码，未指定时自动生成。
            key: 缓存键，未指定时根据 target 自动生成。
            backend: 发送后端类型（email 或 sms）。
            timeout: 验证码有效期（秒）。
            limit: 发送频率限制时间（秒）。
            dryrun: 是否仅模拟发送不实际发送。
            **kwargs: 其他扩展参数。
        """
        self.code = code
        self.target = target
        self.backend = backend
        self.dryrun = dryrun
        self.key = key or self.KEY_TMPL.format(target)
        self.timeout = settings.VERIFY_CODE_TTL if timeout is None else timeout
        self.limit = settings.VERIFY_CODE_LIMIT if limit is None else limit
        self.limit_key = self.RATE_KEY_TMPL.format(target)
        self.other_args = kwargs

    def gen_and_send_async(self) -> str:
        """带频率限制检查的异步生成并发送验证码。"""
        self.__rata()
        return self.gen_and_send()

    def gen_and_send(self) -> str:
        """生成并发送验证码，异常时清理缓存。"""
        try:
            if not self.code:
                self.__generate()
            self.__send()
        except Exception as e:
            self.__clear()
            raise

    def verify(self, code: str) -> bool:
        """验证用户输入的验证码是否正确。

        Args:
            code: 用户输入的验证码。

        Returns:
            验证通过返回 True。

        Raises:
            CodeExpired: 验证码已过期。
            CodeError: 验证码错误。
        """
        right = cache.get(self.key)
        if not right:
            raise CodeExpired

        if right != code:
            raise CodeError

        self.__clear()
        return True

    def __clear(self) -> None:
        """清除验证码与频率限制缓存。"""
        cache.delete(self.key)
        cache.delete(self.limit_key)

    def __ttl(self) -> int:
        """获取验证码剩余有效期。"""
        return cache.ttl(self.key)

    def __rata(self) -> None:
        """检查发送频率限制，超限时抛出异常。"""
        token_send_at = cache.get(self.limit_key, 0)
        if token_send_at:
            raise CodeSendOverRate(cache.ttl(self.limit_key))

    def __get_code(self) -> str | None:
        """从缓存获取当前验证码。"""
        return cache.get(self.key)

    def __generate(self) -> str:
        """生成随机验证码并保存。"""
        code = random_string(settings.VERIFY_CODE_LENGTH, lower=settings.VERIFY_CODE_LOWER_CASE,
                             upper=settings.VERIFY_CODE_UPPER_CASE, digit=settings.VERIFY_CODE_DIGIT_CASE)
        self.code = code
        return code

    def __send_with_sms(self) -> None:
        """通过短信异步发送验证码。"""
        send_sms_async.apply_async(args=(self.target, self.code), priority=100)

    def __send_with_email(self) -> None:
        """通过邮件异步发送验证码。"""
        subject = self.other_args.get('subject', '')
        message = self.other_args.get('message', '')
        send_mail_async.apply_async(
            args=(subject, message, [self.target]),
            kwargs={'html_message': message}, priority=100
        )

    def __send(self) -> None:
        """发送验证码，如有错误直接抛出 API 异常。"""
        if not self.dryrun:
            if self.backend == 'sms':
                self.__send_with_sms()
            else:
                self.__send_with_email()

        cache.set(self.key, self.code, self.timeout)
        cache.set(self.limit_key, self.code, self.limit)
        logger.debug(f'Send verify code to {self.target}')


class TokenTempCache(object):
    """临时令牌缓存工具类。"""

    CACHE_KEY_TOKEN_TEMP_PREFIX = '_KEY_TOKEN_TEMP_CACHE_{}'

    @classmethod
    def generate_cache_token(cls, timeout: int = 3600, data: Any = None) -> str:
        """生成临时缓存令牌并写入缓存。

        Args:
            timeout: 缓存有效期（秒）。
            data: 令牌关联的数据。

        Returns:
            生成的令牌字符串。
        """
        token = random_string(50)
        key = cls.CACHE_KEY_TOKEN_TEMP_PREFIX.format(token)
        cache.set(key, {'time': time.time(), 'data': data}, timeout)
        return token

    @classmethod
    def validate_cache_token(cls, token: str) -> Any:
        """验证临时令牌并返回关联数据。

        Args:
            token: 待验证的令牌字符串。

        Returns:
            令牌关联的数据，无效时返回 None。
        """
        if not token:
            return None
        key = cls.CACHE_KEY_TOKEN_TEMP_PREFIX.format(token)
        value = cache.get(key)
        if not value:
            return None
        try:
            return value.get('data', None)
        except Exception as e:
            logger.error(e, exc_info=True)
            return None

    @classmethod
    def expired_cache_token(cls, token: str) -> None:
        """使临时令牌过期，删除缓存。"""
        key = cls.CACHE_KEY_TOKEN_TEMP_PREFIX.format(token)
        cache.delete(key)
