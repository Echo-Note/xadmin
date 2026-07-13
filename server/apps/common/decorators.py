# -*- coding: utf-8 -*-
#
"""通用装饰器工具集。"""
import asyncio
import functools
import inspect
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any

from django.db import transaction

from apps.common.core.db.utils import open_db_connection
from apps.common.utils import get_logger

logger = get_logger(__name__)


def on_transaction_commit(func: Callable) -> Callable:
    """事务提交后执行函数的装饰器。

    如果不调用 on_commit，对象创建时添加多对多字段值会失败。
    """

    def inner(*args: Any, **kwargs: Any) -> None:
        transaction.on_commit(lambda: func(*args, **kwargs))

    return inner


class Singleton(object):
    """ 单例类 """

    def __init__(self, cls: type) -> None:
        """初始化单例包装器。

        Args:
            cls: 需要包装为单例的类。
        """
        self._cls = cls
        self._instance: dict = {}

    def __call__(self) -> Any:
        """返回单例实例，首次调用时创建。"""
        if self._cls not in self._instance:
            self._instance[self._cls] = self._cls()
        return self._instance[self._cls]


def default_suffix_key(*args: Any, **kwargs: Any) -> str:
    """默认缓存键后缀生成函数。"""
    return 'default'


class EventLoopThread(threading.Thread):
    """运行 asyncio 事件循环的守护线程。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化事件循环线程。"""
        super().__init__(*args, **kwargs)
        self._loop = asyncio.new_event_loop()

    def run(self) -> None:
        """运行事件循环。"""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception as e:
            logger.error("Event loop stopped with err: {} ".format(e))

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """获取事件循环实例。"""
        return self._loop


_loop_thread = EventLoopThread()
_loop_thread.daemon = True
_loop_thread.start()
executor = ThreadPoolExecutor(
    max_workers=10,
    thread_name_prefix='debouncer'
)
_loop_debouncer_func_task_cache: dict = {}
_loop_debouncer_func_args_cache: dict = {}
_loop_debouncer_func_task_time_cache: dict = {}


def get_loop() -> asyncio.AbstractEventLoop:
    """获取全局事件循环实例。"""
    return _loop_thread.get_loop()


def cancel_or_remove_debouncer_task(cache_key: str) -> None:
    """取消或移除防抖任务。

    Args:
        cache_key: 防抖任务缓存键。
    """
    task = _loop_debouncer_func_task_cache.get(cache_key, None)
    if not task:
        return
    if task.done():
        del _loop_debouncer_func_task_cache[cache_key]
    else:
        task.cancel()


def run_debouncer_func(cache_key: str, ttl: float, func: Callable, *args: Any, **kwargs: Any) -> None:
    """执行防抖函数，在 ttl 秒内只执行最后一次。

    Args:
        cache_key: 防抖任务缓存键。
        ttl: 防抖时间窗口（秒）。
        func: 需要防抖执行的函数。
        args: 函数位置参数。
        kwargs: 函数关键字参数。
    """
    cancel_or_remove_debouncer_task(cache_key)
    run_func_partial = functools.partial(_run_func, cache_key, func)

    current = time.time()
    first_run_time = _loop_debouncer_func_task_time_cache.get(cache_key, None)
    if first_run_time is None:
        _loop_debouncer_func_task_time_cache[cache_key] = current
        first_run_time = current

    if current - first_run_time > ttl:
        _loop_debouncer_func_args_cache.pop(cache_key, None)
        _loop_debouncer_func_task_time_cache.pop(cache_key, None)
        executor.submit(run_func_partial, *args, **kwargs)
        logger.debug('pid {} executor submit run {}'.format(
            os.getpid(), func.__name__, ))
        return

    loop = _loop_thread.get_loop()
    _debouncer = Debouncer(run_func_partial, lambda: True, ttl, loop=loop, executor=executor)
    task = asyncio.run_coroutine_threadsafe(_debouncer(*args, **kwargs), loop=loop)
    _loop_debouncer_func_task_cache[cache_key] = task


class Debouncer(object):
    """防抖执行器，延迟执行回调函数。"""

    def __init__(self, callback: Callable, check: Callable, delay: float,
                 loop: asyncio.AbstractEventLoop | None = None,
                 executor: ThreadPoolExecutor | None = None) -> None:
        """初始化防抖执行器。

        Args:
            callback: 延迟执行的回调函数。
            check: 执行前检查函数，返回 True 时执行回调。
            delay: 延迟时间（秒）。
            loop: asyncio 事件循环。
            executor: 线程池执行器。
        """
        self.callback = callback
        self.check = check
        self.delay = delay
        self.loop = loop
        if not loop:
            self.loop = asyncio.get_event_loop()
        self.executor = executor

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """延迟执行回调。"""
        await asyncio.sleep(self.delay)
        ok = await self._run_sync_to_async(self.check)
        if ok:
            callback_func = functools.partial(self.callback, *args, **kwargs)
            return await self._run_sync_to_async(callback_func)

    async def _run_sync_to_async(self, func: Callable) -> Any:
        """将同步函数转为异步执行。

        Args:
            func: 需要执行的函数，可为协程函数。

        Returns:
            函数执行结果。
        """
        if asyncio.iscoroutinefunction(func):
            return await func()
        return await self.loop.run_in_executor(self.executor, func)


ignore_err_exceptions = (
    "(3101, 'Plugin instructed the server to rollback the current transaction.')",
)


def _run_func(key: str, func: Callable, *args: Any, **kwargs: Any) -> None:
    """在新数据库连接中执行函数并处理异常。

    Args:
        key: 防抖任务缓存键。
        func: 需要执行的函数。
        args: 函数位置参数。
        kwargs: 函数关键字参数。
    """
    try:
        with open_db_connection() as conn:
            # 保证执行时使用的是新的 connection 数据库连接
            # 避免出现 MySQL server has gone away 的情况
            func(*args, **kwargs)
    except Exception as e:
        msg = str(e)
        log_func = logger.error
        if msg in ignore_err_exceptions:
            log_func = logger.info
        pid = os.getpid()
        thread_name = threading.current_thread()
        log_func('pid {} thread {} delay run {} error: {}'.format(
            pid, thread_name, func.__name__, msg))
    _loop_debouncer_func_task_cache.pop(key, None)
    _loop_debouncer_func_args_cache.pop(key, None)
    _loop_debouncer_func_task_time_cache.pop(key, None)


def delay_run(ttl: float = 5, key: Callable | None = None) -> Callable:
    """延迟执行函数装饰器，在 ttl 秒内只执行最后一次。

    Args:
        ttl: 防抖时间窗口（秒）。
        key: 缓存键后缀生成回调。

    Returns:
        装饰器函数。
    """

    def inner(func: Callable) -> Callable:
        suffix_key_func = key if key else default_suffix_key
        sigs = inspect.signature(func)
        if len(sigs.parameters) != 0:
            raise ValueError('Merge delay run must not arguments: %s' % func.__name__)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = f'{func.__module__}_{func.__name__}'
            key_suffix = suffix_key_func(*args)
            cache_key = f'DELAY_RUN_{func_name}_{key_suffix}'
            run_debouncer_func(cache_key, ttl, func, *args, **kwargs)

        return wrapper

    return inner


def merge_delay_run(ttl: float = 5, key: Callable | None = None) -> Callable:
    """延迟执行函数装饰器，在 ttl 秒内只执行最后一次，并且合并参数。

    Args:
        ttl: 防抖时间窗口（秒）。
        key: 缓存键后缀生成回调。

    Returns:
        装饰器函数。
    """

    def delay(func: Callable, *args: Any, **kwargs: Any) -> None:
        # 每次调用 delay 时可以指定本次调用的 ttl
        current_ttl = kwargs.pop('ttl', ttl)
        suffix_key_func = key if key else default_suffix_key
        func_name = f'{func.__module__}_{func.__name__}'
        key_suffix = suffix_key_func(*args, **kwargs)
        cache_key = f'MERGE_DELAY_RUN_{func_name}_{key_suffix}'
        cache_kwargs = _loop_debouncer_func_args_cache.get(cache_key, {})

        for k, v in kwargs.items():
            if not isinstance(v, (tuple, list, set)):
                raise ValueError('func kwargs value must be list or tuple: %s %s' % (func.__name__, v))
            v = set(v)
            if k not in cache_kwargs:
                cache_kwargs[k] = v
            else:
                cache_kwargs[k] = cache_kwargs[k].union(v)
        _loop_debouncer_func_args_cache[cache_key] = cache_kwargs
        run_debouncer_func(cache_key, current_ttl, func, *args, **cache_kwargs)

    def apply(func: Callable, sync: bool = False, *args: Any, **kwargs: Any) -> Any:
        """同步或延迟执行函数。

        Args:
            func: 需要执行的函数。
            sync: 是否同步执行。
            args: 函数位置参数。
            kwargs: 函数关键字参数。

        Returns:
            函数执行结果（同步模式下）。
        """
        if sync:
            return func(*args, **kwargs)
        else:
            delay(func, *args, **kwargs)

    def inner(func: Callable) -> Callable:
        sigs = inspect.signature(func)
        if len(sigs.parameters) != 1:
            raise ValueError('func must have one arguments: %s' % func.__name__)
        param = list(sigs.parameters.values())[0]
        if not isinstance(param.default, tuple):
            raise ValueError('func default must be tuple: %s' % param.default)
        func.delay = functools.partial(delay, func)
        func.apply = functools.partial(apply, func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return inner


@delay_run(ttl=5)
def test_delay_run() -> None:
    """延迟执行测试函数。"""
    print("Hello,  now is %s" % time.time())


@merge_delay_run(ttl=5, key=lambda users=(): users[0][0])
def test_merge_delay_run(users: tuple = ()) -> None:
    """合并延迟执行测试函数。"""
    name = ','.join(users)
    time.sleep(2)
    print("Hello, %s, now is %s" % (name, time.time()))


def do_test() -> None:
    """防抖功能测试入口函数。"""
    s = time.time()
    print("start : %s" % time.time())
    for i in range(100):
        # test_delay_run('test', year=i)
        test_merge_delay_run(users=['test %s' % i])
        test_merge_delay_run(users=['best %s' % i])
        test_delay_run('test run %s' % i)

    end = time.time()
    using = end - s
    print("end : %s, using: %s" % (end, using))


def cached_method(ttl: float = 20) -> Callable:
    """内存缓存装饰器，ttl 为缓存时间，-1 表示缓存时间永久。

    Args:
        ttl: 缓存有效期（秒），-1 表示永久。

    Returns:
        装饰器函数。
    """
    _cache: dict = {}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (func, args, tuple(sorted(kwargs.items())))
            # 检查缓存是否存在且未过期
            if key in _cache and (ttl == -1 or time.time() - _cache[key]['timestamp'] < ttl):
                return _cache[key]['result']

            # 缓存过期或不存在，执行方法并缓存结果
            result = func(*args, **kwargs)
            _cache[key] = {'result': result, 'timestamp': time.time()}
            return result

        return wrapper

    return decorator

