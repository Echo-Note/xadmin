#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : security
# author : ly_13
# date : 8/10/2024
"""安全工具类，提供登录限制与 IP 封锁功能。"""


from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.common.utils import ip


class BlockUtil:
    """用户级封锁工具，通过用户名进行登录限制。"""

    BLOCK_KEY_TMPL: str

    def __init__(self, username: str) -> None:
        """初始化封锁工具。

        Args:
            username: 用户名。
        """
        self.block_key = self.BLOCK_KEY_TMPL.format(username)
        self.key_ttl = int(settings.SECURITY_LOGIN_LIMIT_TIME) * 60

    def block(self) -> None:
        """封锁用户。"""
        cache.set(self.block_key, True, self.key_ttl)

    def is_block(self) -> bool:
        """判断用户是否被封锁。"""
        return bool(cache.get(self.block_key))


class BlockUtilBase:
    """登录限制基类，记录失败次数并在达到阈值后封锁。"""

    LIMIT_KEY_TMPL: str
    BLOCK_KEY_TMPL: str

    def __init__(self, username: str, ip: str) -> None:
        """初始化登录限制工具。

        Args:
            username: 用户名。
            ip: 客户端 IP 地址。
        """
        self.username = username
        self.ip = ip
        self.limit_key = self.LIMIT_KEY_TMPL.format(username, ip)
        self.block_key = self.BLOCK_KEY_TMPL.format(username)
        self.key_ttl = int(settings.SECURITY_LOGIN_LIMIT_TIME) * 60

    def get_remainder_times(self) -> int:
        """获取剩余尝试次数。"""
        times_up = settings.SECURITY_LOGIN_LIMIT_COUNT
        times_failed = self.get_failed_count()
        times_remainder = int(times_up) - int(times_failed)
        return times_remainder

    def incr_failed_count(self) -> int:
        """递增失败次数，达到阈值后封锁。

        Returns:
            剩余可用次数。
        """
        limit_key = self.limit_key
        count = cache.get(limit_key, 0)
        count += 1
        cache.set(limit_key, count, self.key_ttl)

        limit_count = settings.SECURITY_LOGIN_LIMIT_COUNT
        if count >= limit_count:
            cache.set(self.block_key, True, self.key_ttl)
        return limit_count - count

    def get_failed_count(self) -> int:
        """获取已失败次数。"""
        count = cache.get(self.limit_key, 0)
        return count

    def clean_failed_count(self) -> None:
        """清除失败次数记录与封锁标记。"""
        cache.delete(self.limit_key)
        cache.delete(self.block_key)

    @classmethod
    def unblock_user(cls, username: str) -> None:
        """解除指定用户的封锁。

        Args:
            username: 用户名。
        """
        key_limit = cls.LIMIT_KEY_TMPL.format(username, '*')
        key_block = cls.BLOCK_KEY_TMPL.format(username)
        # Redis 尽量不要用通配
        cache.delete_pattern(key_limit)
        cache.delete(key_block)

    @classmethod
    def is_user_block(cls, username: str) -> bool:
        """判断指定用户是否被封锁。

        Args:
            username: 用户名。

        Returns:
            用户是否被封锁。
        """
        block_key = cls.BLOCK_KEY_TMPL.format(username)
        return bool(cache.get(block_key))

    def is_block(self) -> bool:
        """判断当前用户是否被封锁。"""
        return bool(cache.get(self.block_key))


class BlockGlobalIpUtilBase:
    """IP 级封锁工具，基于 IP 地址进行登录限制。"""

    LIMIT_KEY_TMPL: str
    BLOCK_KEY_TMPL: str

    def __init__(self, ip: str) -> None:
        """初始化 IP 封锁工具。

        Args:
            ip: 客户端 IP 地址。
        """
        self.ip = ip
        self.limit_key = self.LIMIT_KEY_TMPL.format(ip)
        self.block_key = self.BLOCK_KEY_TMPL.format(ip)
        self.key_ttl = int(settings.SECURITY_LOGIN_IP_LIMIT_TIME) * 60

    @property
    def ip_in_black_list(self) -> bool:
        """判断当前 IP 是否在黑名单中。"""
        return ip.contains_ip(self.ip, settings.SECURITY_LOGIN_IP_BLACK_LIST)

    @property
    def ip_in_white_list(self) -> bool:
        """判断当前 IP 是否在白名单中。"""
        return ip.contains_ip(self.ip, settings.SECURITY_LOGIN_IP_WHITE_LIST)

    def set_block_if_need(self) -> None:
        """在需要时设置 IP 封锁（白名单/黑名单除外）。"""
        if self.ip_in_white_list or self.ip_in_black_list:
            return
        count = cache.get(self.limit_key, 0)
        count += 1
        cache.set(self.limit_key, count, self.key_ttl)

        limit_count = settings.SECURITY_LOGIN_IP_LIMIT_COUNT
        if count < limit_count:
            return
        cache.set(self.block_key, timezone.now().isoformat(), self.key_ttl)

    def clean_block_if_need(self) -> None:
        """清除 IP 封锁记录。"""
        cache.delete(self.limit_key)
        cache.delete(self.block_key)

    def is_block(self) -> bool:
        """判断当前 IP 是否被封锁。"""
        if self.ip_in_white_list:
            return False
        if self.ip_in_black_list:
            return True
        return bool(cache.get(self.block_key))

    def get_block_info(self) -> str:
        """获取 IP 封锁信息。"""
        try:
            data = cache.get(self.block_key)
            if data:
                return parse_datetime(data)
            return "N/A"
        except:
            return "N/A"


class LoginBlockUtil(BlockUtilBase):
    """登录失败封锁工具。"""

    LIMIT_KEY_TMPL = "_LOGIN_LIMIT_{}_{}"
    BLOCK_KEY_TMPL = "_LOGIN_BLOCK_{}"


class ResetBlockUtil(BlockUtilBase):
    """重置密码失败封锁工具。"""

    LIMIT_KEY_TMPL = "_RESET_LIMIT_{}_{}"
    BLOCK_KEY_TMPL = "_RESET_BLOCK_{}"


class RegisterBlockUtil(BlockUtilBase):
    """注册失败封锁工具。"""

    LIMIT_KEY_TMPL = "_REGISTER_LIMIT_{}_{}"
    BLOCK_KEY_TMPL = "_REGISTER_BLOCK_{}"


class SendVerifyCodeBlockUtil(BlockUtilBase):
    """发送验证码频率限制工具。"""

    LIMIT_KEY_TMPL = "_SEND_VERIFY_CODE_LIMIT_{}_{}"
    BLOCK_KEY_TMPL = "_SEND_VERIFY_CODE_BLOCK_{}"


class MFABlockUtils(BlockUtilBase):
    """MFA 验证失败封锁工具。"""

    LIMIT_KEY_TMPL = "_MFA_LIMIT_{}_{}"
    BLOCK_KEY_TMPL = "_MFA_BLOCK_{}"


class LoginIpBlockUtil(BlockGlobalIpUtilBase):
    """登录 IP 封锁工具。"""

    LIMIT_KEY_TMPL = "_LOGIN_LIMIT_{}"
    BLOCK_KEY_TMPL = "_LOGIN_BLOCK_IP_{}"
