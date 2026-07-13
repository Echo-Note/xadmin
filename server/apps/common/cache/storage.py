#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : storage
# author : ly_13
# date : 6/2/2023
"""基于 Django 缓存的存储封装模块，提供通用与业务专用缓存类。"""

from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.common.utils import get_logger

logger = get_logger(__name__)


class RedisCacheBase(object):
    """Redis 缓存基类，封装常用缓存读写操作。"""

    def __init__(self, cache_key: str, timeout: int = 600) -> None:
        """初始化缓存基类。

        Args:
            cache_key: 缓存键。
            timeout: 默认缓存超时时间（秒）。
        """
        self.cache_key = cache_key
        self._timeout = timeout

    def __getattribute__(self, item: str) -> Any:
        """重写属性访问，记录缓存操作日志。"""
        if isinstance(item, str) and item != 'cache_key':
            if hasattr(self, 'cache_key'):
                logger.debug(f'act:{item} cache_key:{super().__getattribute__("cache_key")}')
        return super().__getattribute__(item)

    def get_storage_cache(self, defaults: Any = None) -> Any:
        """获取缓存值。

        Args:
            defaults: 缓存不存在时的默认值。

        Returns:
            缓存值或默认值。
        """
        return cache.get(self.cache_key, defaults)

    def get_storage_key_and_cache(self) -> tuple[str, Any]:
        """获取缓存键与缓存值。

        Returns:
            元组 (缓存键, 缓存值)。
        """
        return self.cache_key, cache.get(self.cache_key)

    def set_storage_cache(self, value: Any, timeout: int = 0) -> None:
        """写入缓存值。

        Args:
            value: 缓存值。
            timeout: 缓存超时时间（秒），为 0 时使用默认超时。
        """
        if isinstance(timeout, int) and timeout == 0:
            timeout = self._timeout
        return cache.set(self.cache_key, value, timeout)

    def append_storage_cache(self, value: Any, timeout: int | None = None) -> None:
        """在缓存列表中追加值，通过锁保证并发安全。

        Args:
            value: 待追加的值。
            timeout: 缓存超时时间（秒），为 None 时使用默认超时。
        """
        with cache.lock(f'{self.cache_key}_lock', timeout=60, blocking_timeout=60):
            data = cache.get(self.cache_key, [])
            data.append(value)
            return cache.set(self.cache_key, data, timeout if timeout else self._timeout)

    def del_storage_cache(self) -> None:
        """删除缓存值。"""
        return cache.delete(self.cache_key)

    def incr(self, amount: int = 1) -> int:
        """缓存值自增。

        Args:
            amount: 自增量。

        Returns:
            自增后的值。
        """
        return cache.incr(self.cache_key, amount)

    def expire(self, timeout: int) -> bool:
        """设置缓存过期时间。

        Args:
            timeout: 过期时间（秒）。

        Returns:
            操作是否成功。
        """
        return cache.expire(self.cache_key, timeout=timeout)

    def iter_keys(self) -> list[str]:
        """遍历匹配的缓存键，自动追加通配符。

        Returns:
            匹配的缓存键列表。
        """
        if not self.cache_key.endswith('*'):
            self.cache_key = f'{self.cache_key}*'
        return cache.iter_keys(self.cache_key)

    def get_many(self) -> dict[str, Any]:
        """批量获取缓存值。

        Returns:
            键值映射字典。
        """
        return cache.get_many(self.cache_key)

    def del_many(self) -> bool:
        """批量删除匹配的缓存键。

        Returns:
            始终返回 True。
        """
        cache.delete_pattern(self.cache_key)
        return True


class TokenManagerCache(RedisCacheBase):
    """令牌管理缓存。"""

    def __init__(self, key: str, release_id: str) -> None:
        """初始化令牌管理缓存。

        Args:
            key: 业务键。
            release_id: 发布标识。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('make_token_key')}_{key.lower()}_{release_id}"
        super().__init__(self.cache_key)


class PendingStateCache(RedisCacheBase):
    """挂起状态缓存。"""

    def __init__(self, locker_key: str) -> None:
        """初始化挂起状态缓存。

        Args:
            locker_key: 锁键。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('pending_state_key')}_{locker_key}"
        super().__init__(self.cache_key)


class UploadPartInfoCache(RedisCacheBase):
    """上传分片信息缓存。"""

    def __init__(self, locker_key: str) -> None:
        """初始化上传分片信息缓存。

        Args:
            locker_key: 锁键。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('upload_part_info_key')}_{locker_key}"
        super().__init__(self.cache_key)


class DownloadUrlCache(RedisCacheBase):
    """下载地址缓存。"""

    def __init__(self, drive_id: str, file_id: str) -> None:
        """初始化下载地址缓存。

        Args:
            drive_id: 网盘 ID。
            file_id: 文件 ID。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('download_url_key')}_{drive_id}_{file_id}"
        super().__init__(self.cache_key)


class BlackAccessTokenCache(RedisCacheBase):
    """黑名单访问令牌缓存。"""

    def __init__(self, user_id: str, access_key: str) -> None:
        """初始化黑名单访问令牌缓存。

        Args:
            user_id: 用户 ID。
            access_key: 访问密钥。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('black_access_token_key')}_{user_id}_{access_key}"
        super().__init__(self.cache_key)


class UserSystemConfigCache(RedisCacheBase):
    """用户系统配置缓存。"""

    def __init__(self, prefix_key: str) -> None:
        """初始化用户系统配置缓存。

        Args:
            prefix_key: 前缀键。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('config_key')}_{prefix_key}"
        super().__init__(self.cache_key)


class CommonResourceIDsCache(RedisCacheBase):
    """公共资源 ID 缓存。"""

    def __init__(self, prefix_key: str) -> None:
        """初始化公共资源 ID 缓存。

        Args:
            prefix_key: 前缀键。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('common_resource_ids_key')}_{prefix_key}"
        super().__init__(self.cache_key)


class WebSocketMsgResultCache(RedisCacheBase):
    """WebSocket 消息结果缓存。"""

    def __init__(self, prefix_key: str) -> None:
        """初始化 WebSocket 消息结果缓存。

        Args:
            prefix_key: 前缀键。
        """
        self.cache_key = f"{settings.CACHE_KEY_TEMPLATE.get('websocket_message_result_key')}_{prefix_key}"
        super().__init__(self.cache_key)
