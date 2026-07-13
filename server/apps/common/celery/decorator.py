#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : decorator
# author : ly_13
# date : 9/14/2024
"""Celery 定时任务注册装饰器。"""

from collections.abc import Callable
from functools import wraps
from typing import Any

_need_registered_period_tasks: list[dict] = []
_after_app_ready_start_tasks: list[str] = []
_after_app_shutdown_clean_periodic_tasks: list[str] = []


def add_register_period_task(task: dict) -> None:
    """添加需要注册的定时任务配置。

    Args:
        task: 定时任务配置字典。
    """
    _need_registered_period_tasks.append(task)


def get_register_period_tasks() -> list[dict]:
    """获取所有需要注册的定时任务配置列表。"""
    return _need_registered_period_tasks


def add_after_app_shutdown_clean_task(name: str) -> None:
    """添加应用关闭时需要清理的定时任务名称。

    Args:
        name: 定时任务名称。
    """
    _after_app_shutdown_clean_periodic_tasks.append(name)


def get_after_app_shutdown_clean_tasks() -> list[str]:
    """获取应用关闭时需要清理的定时任务名称列表。"""
    return _after_app_shutdown_clean_periodic_tasks


def add_after_app_ready_task(name: str) -> None:
    """添加应用就绪后需要启动的任务名称。

    Args:
        name: 任务名称。
    """
    _after_app_ready_start_tasks.append(name)


def get_after_app_ready_tasks() -> list[str]:
    """获取应用就绪后需要启动的任务名称列表。"""
    return _after_app_ready_start_tasks


def register_as_period_task(
        crontab: str | None = None, interval: int | None = None, name: str | None = None,
        args: tuple = (), kwargs: dict | None = None,
        description: str = '') -> Callable:
    """注册为 Celery 定时任务的装饰器。

    Args:
        crontab: crontab 表达式，如 "* * * * *"。
        interval: 间隔秒数，如 60。
        name: 定时任务名称。
        args: 任务位置参数。
        kwargs: 任务关键字参数。
        description: 任务描述。

    Returns:
        装饰器函数。
    """
    if crontab is None and interval is None:
        raise SyntaxError("Must set crontab or interval one")

    def decorate(func: Callable) -> Callable:
        if crontab is None and interval is None:
            raise SyntaxError("Interval and crontab must set one")

        # Because when this decorator run, the task was not created,
        # So we can't use func.name
        task = '{func.__module__}.{func.__name__}'.format(func=func)
        _name = name if name else task
        add_register_period_task({
            _name: {
                'task': task,
                'interval': interval,
                'crontab': crontab,
                'args': args,
                'kwargs': kwargs if kwargs else {},
                'description': description
            }
        })

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return decorate


def after_app_ready_start(func: Callable) -> Callable:
    """标记任务在应用就绪后启动的装饰器。"""
    # Because when this decorator run, the task was not created,
    # So we can't use func.name
    name = '{func.__module__}.{func.__name__}'.format(func=func)
    if name not in _after_app_ready_start_tasks:
        add_after_app_ready_task(name)

    @wraps(func)
    def decorate(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return decorate


def after_app_shutdown_clean_periodic(func: Callable) -> Callable:
    """标记任务在应用关闭时清理的装饰器。"""
    # Because when this decorator run, the task was not created,
    # So we can't use func.name
    name = '{func.__module__}.{func.__name__}'.format(func=func)
    if name not in _after_app_shutdown_clean_periodic_tasks:
        add_after_app_shutdown_clean_task(name)

    @wraps(func)
    def decorate(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return decorate
