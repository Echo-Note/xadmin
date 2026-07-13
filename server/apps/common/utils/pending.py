#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : pending
# author : ly_13
# date : 6/2/2023
"""请求挂起与并发控制工具模块。"""

import time
from collections.abc import Callable
from typing import Any

from django.core.cache import cache

from apps.common.cache.storage import PendingStateCache
from apps.common.utils import get_logger

logger = get_logger(__name__)


def set_pending_cache(unique_key: str, cache_data: list[str], cache_obj: PendingStateCache, timeout: int) -> None:
    """更新挂起缓存，移除已完成的唯一标识后写回缓存。

    Args:
        unique_key: 请求唯一标识。
        cache_data: 当前挂起的唯一标识列表。
        cache_obj: 挂起状态缓存对象。
        timeout: 缓存超时时间（秒）。
    """
    if unique_key in cache_data:
        cache_data.remove(unique_key)
    logger.warning(f'return unique_key:{unique_key}  cache_data: {cache_data}  ')
    cache_obj.set_storage_cache(cache_data, timeout)


def get_pending_result(
    func: Callable[..., Any],
    expect_func: Callable[..., bool],
    loop_count: int = 10,
    sleep_time: int = 3,
    unique_key: str = 'default_key',
    run_func_count: int = 2,
    pop_first: bool = True,
    *args: Any,
    **kwargs: Any,
) -> tuple[bool, dict[str, Any]]:
    """在并发请求场景下轮询执行函数并返回预期结果。

    通过缓存锁与唯一标识控制并发请求数量，超出阈值时自动移除等待中的请求。

    Args:
        func: 将要运行的目标函数对象。
        expect_func: 期待结果的判断函数，返回 True 表示满足预期。
        loop_count: 最大轮询执行次数。
        sleep_time: 每次轮询间隔时间（秒）。
        unique_key: 请求唯一标识，用于函数并发请求控制。
        run_func_count: 函数并发请求数上限，超过该次数会自动移除多余等待。
        pop_first: 超出时是否移除最老的请求，True 移除最老，False 移除最新。
        *args: 传递给 func 和 expect_func 的位置参数。
        **kwargs: 传递给 func 和 expect_func 的关键字参数，需包含 locker_key。

    Returns:
        元组 (是否成功, 结果字典)。
    """
    locker_key = kwargs.pop('locker_key')
    cache_timeout = loop_count * sleep_time * (run_func_count + 1)
    cache_obj = PendingStateCache(locker_key)
    cache_data = cache_obj.get_storage_cache()
    is_pop = False
    if cache_data and isinstance(cache_data, list):
        if unique_key not in cache_data:
            cache_data.append(unique_key)
            if len(cache_data) > run_func_count and len(cache_data) > 0:
                is_pop = True
                if pop_first:
                    cache_data.pop(0)
                else:
                    cache_data.pop()
    else:
        cache_data = [unique_key]

    cache_obj.set_storage_cache(cache_data, cache_timeout)
    if not pop_first and len(cache_data) == run_func_count and is_pop:
        logger.warning(f'unique_key:{unique_key}  cache_data: {cache_data}  ')
        return True, {'err_msg': '请求重复,请稍后再试'}
    try:
        with cache.lock(f'get_pending_result_{locker_key}', timeout=loop_count * sleep_time):
            count = 1
            while True:
                cache_data = cache_obj.get_storage_cache()
                logger.warning(f'unique_key:{unique_key}  cache_data: {cache_data}  ')
                if cache_data and isinstance(cache_data, list) and unique_key in cache_data:
                    result = func(*args, **kwargs)
                    if expect_func(result, *args, **kwargs):
                        set_pending_cache(unique_key, cache_data, cache_obj, cache_timeout)
                        return True, {'data': result}
                    time.sleep(sleep_time)
                    if loop_count < count:
                        set_pending_cache(unique_key, cache_data, cache_obj, cache_timeout)
                        return False, {'err_msg': '请求超时'}
                    count += 1
                else:
                    set_pending_cache(unique_key, cache_data, cache_obj, cache_timeout)
                    return True, {'err_msg': '请求重复,请稍后再试'}

    except Exception as e:
        logger.warning(f'get pending result exception: {e}')
        set_pending_cache(unique_key, cache_data, cache_obj, cache_timeout)
        return False, {'err_msg': '内部错误'}
