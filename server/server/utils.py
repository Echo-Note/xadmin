#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : utils
# author : ly_13
# date : 10/18/2024
"""服务端工具函数模块，提供线程级请求上下文与数据库表前缀注入等功能。"""

from typing import Any

from django.conf import settings
from django.db import connection
from django.db.backends.utils import truncate_name
from django.db.models import Model
from django.db.models.signals import class_prepared
from django.http import HttpRequest

from apps.common.local import thread_local


def set_current_request(request: HttpRequest) -> None:
    """将当前请求对象保存到线程局部存储中，供日志等模块获取。

    Args:
        request: 当前 HTTP 请求对象。
    """
    setattr(thread_local, 'current_request', request)


def _find(attr: str) -> Any:
    """从线程局部存储中按属性名查找值。

    Args:
        attr: 属性名称。

    Returns:
        属性值，不存在时返回 None。
    """
    return getattr(thread_local, attr, None)


def get_current_request() -> HttpRequest | None:
    """获取当前线程关联的 HTTP 请求对象。

    Returns:
        当前请求对象，未设置时返回 None。
    """
    return _find('current_request')


def add_db_prefix(sender: type[Model], **kwargs: Any) -> None:
    """在模型类准备完成时，根据配置为其数据库表名添加前缀。

    Args:
        sender: 触发信号的模型类。
        **kwargs: 信号附带的关键字参数。
    """
    prefix = settings.DB_PREFIX
    meta = sender._meta
    if not meta.managed:
        return
    if isinstance(prefix, dict):
        app_label = meta.app_label.lower()
        if meta.label_lower in prefix:
            prefix = prefix[meta.label_lower]
        elif meta.label in prefix:
            prefix = prefix[meta.label]
        elif app_label in prefix:
            prefix = prefix[app_label]
        else:
            prefix = prefix.get("", None)
    if prefix and not meta.db_table.startswith(prefix):
        meta.db_table = truncate_name("%s%s" % (prefix, meta.db_table), connection.ops.max_name_length())


class_prepared.connect(add_db_prefix)
