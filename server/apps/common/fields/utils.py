#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : utils
# author : ly_13
# date : 7/25/2024
"""字段工具函数。"""
from collections.abc import Callable
from functools import wraps

from django.db.models.fields.files import FieldFile
from django.http import HttpRequest
from rest_framework.fields import Field as RFField


def get_file_absolute_uri(value: FieldFile, request: HttpRequest | None = None, use_url: bool = True) -> str | None:
    """获取文件的绝对 URI 或文件名。

    Args:
        value: 文件字段对象。
        request: HTTP 请求对象，用于构建绝对 URI。
        use_url: 是否返回 URL，False 时返回文件名。

    Returns:
        文件绝对 URI 或文件名，文件为空时返回 None。
    """
    if not value:
        return None

    if use_url:
        try:
            url = value.url
        except AttributeError:
            return None
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    return value.name


def input_wrapper(func: Callable) -> Callable:
    """为序列化器字段增加 input_type 参数，用于前端识别。

    Args:
        func: 字段类构造函数。

    Returns:
        包装后的字段构造函数。
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> RFField:
        class Field(func):
            def __init__(self, *_args, **_kwargs):
                self.input_type = _kwargs.pop("input_type", '')
                super().__init__(*_args, **_kwargs)

        return Field(*args, **kwargs)

    return wrapper

