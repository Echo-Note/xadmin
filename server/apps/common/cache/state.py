#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : state
# author : ly_13
# date : 6/2/2023
"""基于缓存的互斥状态控制模块。"""

import time
from types import TracebackType
from typing import Any

from django.core.cache import cache

from apps.common.utils import get_logger

logger = get_logger(__name__)


class CacheBaseState(object):
    """基于 Django 缓存的互斥状态基类，支持上下文管理器用法。"""

    def __init__(self, key: str, value: float = time.time(), timeout: int = 3600 * 24) -> None:
        """初始化缓存状态。

        Args:
            key: 缓存键。
            value: 缓存值。
            timeout: 缓存超时时间（秒）。
        """
        self.key = f'CacheBaseState_{self.__class__.__name__}_{key}'
        self.value = value
        self.timeout = timeout
        self.active = False

    def get_state(self) -> Any:
        """获取当前缓存状态值。"""
        return cache.get(self.key)

    def del_state(self) -> None:
        """删除当前缓存状态。"""
        return cache.delete(self.key)

    def __enter__(self) -> bool:
        """进入上下文时尝试获取锁，已锁定则返回 False。"""
        if cache.get(self.key):
            return False
        else:
            cache.set(self.key, self.value, self.timeout)
            self.active = True
        return True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """退出上下文时释放锁（仅在持有时）。"""
        if self.active:
            cache.delete(self.key)
        logger.info(f'cache base state __exit__ {exc_type}, {exc_val}, {exc_tb}')


class SyncDriveSizeState(CacheBaseState):
    """同步网盘容量状态锁。"""
    ...


class GetDriveAuthCache(CacheBaseState):
    """获取网盘授权缓存状态锁。"""
    ...
