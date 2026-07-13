#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : local
# author : ly_13
# date : 10/18/2024
"""线程本地存储工具。"""


from typing import Any

from asgiref.local import Local

thread_local = Local(thread_critical=True)


def _find(attr: str) -> Any:
    """从线程本地存储中获取指定属性值。

    Args:
        attr: 属性名。

    Returns:
        属性值，不存在时返回 None。
    """
    return getattr(thread_local, attr, None)

