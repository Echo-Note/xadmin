#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : magic
# author : ly_13
# date : 6/2/2023
"""通用魔法装饰器与缓存工具模块。

本模块提供了一系列装饰器函数和缓存类，用于函数加锁执行、重试机制、
调用次数限制、缓存数据/响应、数据库连接管理、信号临时禁用以及 SQL 计数等功能。
"""


import functools
import time
from collections.abc import Callable
from functools import wraps, WRAPPER_ASSIGNMENTS
from importlib import import_module
from typing import Any

from django.core.cache import cache
from django.db import close_old_connections, connection
from django.http.response import HttpResponse

from apps.common.utils import get_logger

logger = get_logger(__name__)


def run_function_by_locker(timeout: int = 60 * 5, lock_func: Callable | None = None) -> Callable:
    """通过分布式锁装饰函数，保证同一时刻仅有一个实例执行。

    Args:
        timeout: 锁的超时时间，单位秒，默认为 5 分钟。
        lock_func: 可选的锁键生成函数，返回包含 ``locker_key`` 的字典；为 None 时
            从被装饰函数的 ``locker`` 关键字参数中获取。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            if lock_func:
                locker = lock_func(*args, **kwargs)
            else:
                locker = kwargs.get('locker', {})
                if locker:
                    kwargs.pop('locker')
            t_locker = {'timeout': timeout, 'locker_key': func.__name__}
            t_locker.update(locker)
            new_locker_key = t_locker.pop('locker_key')
            new_timeout = t_locker.pop('timeout')
            if locker and new_timeout and new_locker_key:
                with cache.lock(new_locker_key, timeout=new_timeout, **t_locker):
                    logger.info(f"{new_locker_key} exec {func} start. now time:{time.time()}")
                    res = func(*args, **kwargs)
            else:
                res = func(*args, **kwargs)
            logger.debug(f"{new_locker_key} exec {func} finished. used time:{time.time() - start_time} result:{res}")
            return res

        return wrapper

    return decorator


def call_function_try_attempts(
    try_attempts: int = 3,
    sleep_time: int = 2,
    failed_callback: Callable | None = None,
) -> Callable:
    """装饰函数，在失败时自动重试指定次数。

    Args:
        try_attempts: 最大尝试次数，默认为 3。
        sleep_time: 每次重试之间的间隔秒数，默认为 2。
        failed_callback: 全部尝试失败后执行的回调函数，接收原函数参数及 ``result`` 关键字参数。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> tuple[bool, Any]:
            res = False, {}
            start_time = time.time()
            for i in range(try_attempts):
                res = func(*args, **kwargs)
                status, result = res
                if status:
                    return res
                else:
                    logger.warning(f'exec {func} failed. {try_attempts} times in total. now {sleep_time} later try '
                                   f'again...{i}')
                time.sleep(sleep_time)
            if not res[0]:
                logger.error(f'exec {func} failed after the maximum number of attempts. Failed:{res[1]}')
                if failed_callback:
                    logger.error(f'exec {func} failed and exec failed callback {failed_callback.__name__}')
                    failed_callback(*args, **kwargs, result=res)
            logger.debug(f"exec {func} finished. time:{time.time() - start_time} result:{res}")
            return res

        return wrapper

    return decorator


def magic_wrapper(func: Callable, *args: Any, **kwargs: Any) -> Callable:
    """将函数及其参数封装为一个无参可调用对象。

    Args:
        func: 待封装的目标函数。
        *args: 传递给目标函数的位置参数。
        **kwargs: 传递给目标函数的关键字参数。

    Returns:
        封装后的无参包装函数。
    """
    @wraps(func)
    def wrapper() -> Any:
        return func(*args, **kwargs)

    return wrapper


def import_from_string(dotted_path: str) -> Any:
    """根据点分模块路径导入并返回对应的属性或类。

    Args:
        dotted_path: 形如 ``package.module.attr`` 的点分路径字符串。

    Returns:
        路径末段指定的属性或类对象。

    Raises:
        ImportError: 路径格式不合法或目标属性不存在时抛出。
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute/class') from err


def magic_call_in_times(
    call_time: int = 24 * 3600,
    call_limit: int = 6,
    key: Callable | None = None,
) -> Callable:
    """限制函数在指定时间窗口内的调用次数。

    Args:
        call_time: 统计时间窗口，单位秒，默认为 24 小时。
        call_limit: 时间窗口内允许的最大调用次数，默认为 6。
        key: 可选的缓存键生成函数，用于区分不同调用场景。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> tuple[bool, Any]:
            cache_key = f'magic_call_in_times_{func.__name__}'
            if key:
                cache_key = f'{cache_key}_{key(*args, **kwargs)}'
            cache_data = cache.get(cache_key)
            if cache_data:
                if cache_data > call_limit:
                    err_msg = f'{func} not yet started. cache_key:{cache_key} call over limit {call_limit} in {call_time}'
                    logger.warning(err_msg)
                    return False, err_msg
                else:
                    cache.incr(cache_key, 1)
            else:
                cache.set(cache_key, 1, call_time)
            start_time = time.time()
            try:
                res = func(*args, **kwargs)
                logger.debug(
                    f"exec {func} finished. time:{time.time() - start_time}  cache_key:{cache_key} result:{res}")
                status = True
            except Exception as e:
                res = str(e)
                logger.info(f"exec {func} failed. time:{time.time() - start_time}  cache_key:{cache_key} Exception:{e}")
                status = False

            return status, res

        return wrapper

    return decorator


class MagicCacheData(object):
    """数据级缓存工具类，提供基于缓存的函数结果存储与失效管理。"""

    @staticmethod
    def make_cache(
        timeout: int = 60 * 10,
        invalid_time: int = 0,
        key_func: Callable | None = None,
        timeout_func: Callable | None = None,
    ) -> Callable:
        """静态方法装饰器，为函数添加数据缓存能力。

        Args:
            timeout: 数据缓存时长，单位秒。
            invalid_time: 数据缓存提前失效时间，单位秒。实际有效时间为 ``timeout - invalid_time``。
            key_func: 缓存唯一标识生成函数，默认为所装饰函数名称。
            timeout_func: 动态计算缓存时长的函数。

        Returns:
            装饰器函数。
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = f'magic_cache_data_{func.__name__}'
                if key_func:
                    cache_key = f'{cache_key}_{key_func(*args, **kwargs)}'

                cache_time = timeout
                if timeout_func:
                    cache_time = timeout_func(*args, **kwargs)
                n_time = time.time()
                res = cache.get(cache_key)
                if res:
                    while not res or res.get('status') != 'ok':
                        time.sleep(0.5)
                        logger.warning(
                            f'exec {func} wait. data status is not ok. cache_time:{cache_time} cache_key:{cache_key}  cache data exist result:{res}')
                        res = cache.get(cache_key)
                with cache.lock(f"locker_{cache_key}", timeout=cache_time - invalid_time):
                    if res and n_time - res.get('c_time', n_time) < cache_time - invalid_time:
                        logger.debug(
                            f"exec {func} finished. cache_time:{cache_time} cache_key:{cache_key} cache data exist result:{res}")
                        return res['data']
                    else:
                        res = {'c_time': n_time, 'data': '', 'status': 'ready'}
                        cache.set(cache_key, res, cache_time)
                        try:
                            res['data'] = func(*args, **kwargs)
                            logger.debug(
                                f"exec {func} finished. time:{time.time() - n_time} cache_time:{cache_time} cache_key:{cache_key} result:{res}")
                        except Exception as e:
                            logger.error(
                                f"exec {func} failed. time:{time.time() - n_time}  cache_time:{cache_time} cache_key:{cache_key} Exception:{e}")

                        res['status'] = 'ok'
                        cache.set(cache_key, res, cache_time)

                        return res['data']

            return wrapper

        return decorator

    @staticmethod
    def invalid_cache(key: str) -> None:
        """根据键名失效对应的数据缓存。

        Args:
            key: 缓存键名（不含前缀）。
        """
        cache_key = f'magic_cache_data_{key}'
        count = cache.delete_pattern(cache_key)
        logger.warning(f"invalid_cache cache_key:{cache_key} count:{count}")

    @staticmethod
    def invalid_caches(keys: list[str]) -> None:
        """批量失效多个数据缓存。

        Args:
            keys: 需要失效的缓存键名列表（不含前缀）。
        """
        delete_keys = [f'magic_cache_data_{key}' for key in keys]
        count = cache.delete_many(delete_keys)
        logger.warning(
            f"invalid_cache_data cache_key:{delete_keys[0]}... {len(delete_keys)} count. delete count:{count}")


class MagicCacheResponse(object):
    """视图响应级缓存工具类，用于缓存 DRF 视图方法的完整 HTTP 响应。"""

    def __init__(self, timeout: int = 60 * 10, invalid_time: int = 0, key_func: Callable | str | None = None) -> None:
        """初始化响应缓存实例。

        Args:
            timeout: 响应缓存时长，单位秒，默认为 10 分钟。
            invalid_time: 缓存提前失效时间，单位秒。
            key_func: 缓存键生成函数或视图实例上的方法名。
        """
        self.timeout = timeout
        self.key_func = key_func
        self.invalid_time = invalid_time

    @staticmethod
    def invalid_cache(key: str) -> None:
        """根据键名失效对应的响应缓存。

        Args:
            key: 缓存键名（不含前缀）。
        """
        cache_key = f'magic_cache_response_{key}'
        count = cache.delete_pattern(cache_key)
        logger.warning(f"invalid_response_cache cache_key:{cache_key} count:{count}")

    @staticmethod
    def invalid_caches(keys: list[str]) -> None:
        """批量失效多个响应缓存。

        Args:
            keys: 需要失效的缓存键名列表（不含前缀）。
        """
        delete_keys = [f'magic_cache_response_{key}' for key in keys]
        count = cache.delete_many(delete_keys)
        logger.warning(
            f"invalid_response_cache cache_key:{delete_keys[0]}... {len(delete_keys)} count. delete count:{count}")

    def __call__(self, func: Callable) -> Callable:
        """将实例作为装饰器调用，包装视图方法以添加响应缓存。

        Args:
            func: 被装饰的视图方法。

        Returns:
            包装后的视图方法。
        """
        this = self

        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        def inner(self: Any, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
            return this.process_cache_response(
                view_instance=self,
                view_method=func,
                request=request,
                args=args,
                kwargs=kwargs,
            )

        return inner

    def process_cache_response(
        self,
        view_instance: Any,
        view_method: Callable,
        request: Any,
        args: tuple,
        kwargs: dict,
    ) -> HttpResponse:
        """处理视图方法的缓存逻辑，命中缓存则返回缓存响应，否则执行视图并缓存结果。

        Args:
            view_instance: 视图实例对象。
            view_method: 原始视图方法。
            request: HTTP 请求对象。
            args: 视图方法位置参数。
            kwargs: 视图方法关键字参数。

        Returns:
            渲染后的 HTTP 响应对象。
        """
        func_key = self.calculate_key(
            view_instance=view_instance,
            view_method=view_method,
            request=request,
            args=args,
            kwargs=kwargs
        )
        cache_key = 'magic_cache_response'
        func_name = f'{view_instance.__class__.__name__}_{view_method.__name__}'
        if func_key:
            cache_key = f'{cache_key}_{func_key}'
        else:
            cache_key = f'{cache_key}_{func_name}'
        timeout = self.calculate_timeout(view_instance=view_instance)
        n_time = time.time()
        if getattr(request, 'no_cache', False):
            res = None
        else:
            res = cache.get(cache_key)
        if res and n_time - res.get('c_time', n_time) < timeout - self.invalid_time:
            logger.info(f"exec {func_name} finished. cache_key:{cache_key}  cache data exist")
            content, status, headers = res['data']
            response = HttpResponse(content=content, status=status)
            response.renderer_context = view_instance.get_renderer_context()
            for k, v in headers.values():
                response[k] = v
        else:
            response = view_method(view_instance, request, *args, **kwargs)
            response = view_instance.finalize_response(request, response, *args, **kwargs)
            response.render()

            if not response.status_code >= 400 and not getattr(request, 'no_cache', False):
                data = (
                    response.rendered_content,
                    response.status_code,
                    {k: (k, v) for k, v in response.items()}
                )
                res = {'c_time': n_time, 'data': data}
                cache.set(cache_key, res, timeout)
                logger.debug(
                    f"exec {func_name} finished. time:{time.time() - n_time}  cache_key:{cache_key} result:{res}")

        if not hasattr(response, '_closable_objects'):
            response._closable_objects = []

        return response

    def calculate_key(
        self,
        view_instance: Any,
        view_method: Callable,
        request: Any,
        args: tuple,
        kwargs: dict,
    ) -> str | None:
        """计算响应缓存的唯一键。

        Args:
            view_instance: 视图实例对象。
            view_method: 原始视图方法。
            request: HTTP 请求对象。
            args: 视图方法位置参数。
            kwargs: 视图方法关键字参数。

        Returns:
            缓存键字符串，若未配置 key_func 则返回 None。
        """
        if isinstance(self.key_func, str):
            key_func = getattr(view_instance, self.key_func)
        else:
            key_func = self.key_func
        if key_func:
            return key_func(
                view_instance=view_instance,
                view_method=view_method,
                request=request,
                args=args,
                kwargs=kwargs,
            )

    def calculate_timeout(self, view_instance: Any, **_: Any) -> int:
        """计算响应缓存的超时时间。

        Args:
            view_instance: 视图实例对象。
            **_: 忽略的其他关键字参数。

        Returns:
            缓存超时时间（秒）。
        """
        if isinstance(self.timeout, str):
            self.timeout = getattr(view_instance, self.timeout)
        return self.timeout


cache_response = MagicCacheResponse


def handle_db_connections(func: Callable) -> Callable:
    """装饰函数，在执行前后关闭旧数据库连接，避免连接泄漏。

    Args:
        func: 待装饰的目标函数。

    Returns:
        包装后的函数。
    """
    @wraps(func)
    def func_wrapper(*args: Any, **kwargs: Any) -> Any:
        close_old_connections()
        logger.info(f'{func.__name__} run before do close old connection')
        result = func(*args, **kwargs)
        logger.info(f'{func.__name__} run after do close old connection')
        close_old_connections()

        return result

    return func_wrapper


def temporary_disable_signal(signal: Any, receiver: Callable, *args: Any, **kwargs: Any) -> Callable:
    """临时禁用信号装饰器，在函数执行期间断开信号，执行完毕后重新连接。

    Args:
        signal: Django 信号实例。
        receiver: 信号接收者函数。
        *args: 传递给 ``signal.disconnect`` / ``signal.connect`` 的位置参数。
        **kwargs: 传递给 ``signal.disconnect`` / ``signal.connect`` 的关键字参数。

    Returns:
        装饰器函数。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*_args: Any, **_kwargs: Any) -> Any:
            signal.disconnect(receiver=receiver, *args, **kwargs)
            try:
                return func(*_args, **_kwargs)
            finally:
                signal.connect(receiver=receiver, *args, **kwargs)

        return wrapper

    return decorator


def timeit(func: Callable) -> Callable:
    """装饰函数，记录目标函数的执行耗时。

    Args:
        func: 待装饰的目标函数。

    Returns:
        包装后的函数。
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} run time:{end_time - start_time}")
        return result

    return wrapper


class SQLCounter:
    """SQL 查询计数器，配合 ``connection.execute_wrapper`` 统计 SQL 执行次数。"""

    def __init__(self) -> None:
        """初始化计数器，将计数置为 0。"""
        self.count = 0

    def __call__(self, execute: Callable, sql: str, params: Any, many: bool, context: Any) -> Any:
        """在每次 SQL 执行时递增计数。

        Args:
            execute: 实际执行 SQL 的回调函数。
            sql: SQL 语句字符串。
            params: SQL 参数。
            many: 是否批量执行。
            context: 执行上下文。

        Returns:
            SQL 执行结果。
        """
        self.count += 1
        return execute(sql, params, many, context)


def count_sql_queries(func: Callable) -> Callable:
    """装饰函数，统计目标函数执行过程中的 SQL 查询次数。

    Args:
        func: 待装饰的目标函数。

    Returns:
        包装后的函数。
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        sql_counter = SQLCounter()
        with connection.execute_wrapper(sql_counter):
            result = func(*args, **kwargs)
        logger.info(f"{func.__name__} sql queries count: {sql_counter.count}")
        return result

    return wrapper
