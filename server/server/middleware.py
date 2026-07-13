#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : middleware
# author : ly_13
# date : 10/18/2024
"""Django 中间件模块，提供 SQL 计数、请求计时、请求上下文与 Referer 校验等中间件。"""

import json
import re
import time
import uuid
from collections.abc import Callable

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse, HttpResponseForbidden, HttpRequest

from .utils import set_current_request


class SQLCountMiddleware:
    """SQL 查询计数中间件，在 DEBUG 模式下统计每个请求的 SQL 查询数量。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """初始化中间件。

        Args:
            get_response: 下一个中间件或视图的可调用对象。
        """
        self.get_response = get_response
        if not settings.DEBUG:
            raise MiddlewareNotUsed

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """处理请求并添加 SQL 查询计数响应头。

        Args:
            request: HTTP 请求对象。

        Returns:
            HTTP 响应对象。
        """
        from django.db import connection
        response = self.get_response(request)
        response['X-SQL-COUNT'] = len(connection.queries) - 2
        return response


class StartMiddleware:
    """请求开始计时中间件，在 DEBUG_DEV 模式下记录请求处理各阶段耗时。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """初始化中间件。

        Args:
            get_response: 下一个中间件或视图的可调用对象。
        """
        self.get_response = get_response
        if not settings.DEBUG_DEV:
            raise MiddlewareNotUsed

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """记录请求开始时间，并在健康检查接口中注入各阶段耗时信息。

        Args:
            request: HTTP 请求对象。

        Returns:
            HTTP 响应对象。
        """
        request._s_time_start = time.time()
        response = self.get_response(request)
        request._s_time_end = time.time()
        if request.path == '/api/common/api/health':
            data = response.data
            data['pre_middleware_time'] = request._e_time_start - request._s_time_start
            data['api_time'] = request._e_time_end - request._e_time_start
            data['post_middleware_time'] = request._s_time_end - request._e_time_end
            response.content = json.dumps(data)
            response.headers['Content-Length'] = str(len(response.content))
            response.headers['Content-Type'] = "application/json"
        return response


class EndMiddleware:
    """请求结束计时中间件，在 DEBUG_DEV 模式下记录视图处理阶段的起止时间。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """初始化中间件。

        Args:
            get_response: 下一个中间件或视图的可调用对象。
        """
        self.get_response = get_response
        if not settings.DEBUG_DEV:
            raise MiddlewareNotUsed

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """记录视图处理阶段的开始与结束时间。

        Args:
            request: HTTP 请求对象。

        Returns:
            HTTP 响应对象。
        """
        request._e_time_start = time.time()
        response = self.get_response(request)
        request._e_time_end = time.time()
        return response


class RequestMiddleware:
    """请求上下文中间件，为每个请求生成唯一标识并写入线程局部存储。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """初始化中间件。

        Args:
            get_response: 下一个中间件或视图的可调用对象。
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """为请求生成唯一 UUID 并设置到线程上下文。

        Args:
            request: HTTP 请求对象。

        Returns:
            HTTP 响应对象。
        """
        request.request_uuid = uuid.uuid4()
        set_current_request(request)
        response = self.get_response(request)
        return response


class RefererCheckMiddleware:
    """Referer 校验中间件，防止跨站请求伪造。"""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """初始化中间件并编译 Referer 匹配正则。

        Args:
            get_response: 下一个中间件或视图的可调用对象。
        """
        if not settings.REFERER_CHECK_ENABLED:
            raise MiddlewareNotUsed
        self.get_response = get_response
        self.http_pattern = re.compile('https?://')

    def check_referer(self, request: HttpRequest) -> bool:
        """校验请求的 Referer 是否与当前主机匹配。

        Args:
            request: HTTP 请求对象。

        Returns:
            Referer 合法时返回 True，否则返回 False。
        """
        referer = request.META.get('HTTP_REFERER', '')
        referer = self.http_pattern.sub('', referer)
        if not referer:
            return True
        remote_host = request.get_host()
        return referer.startswith(remote_host)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """处理请求，Referer 校验失败时返回 403。

        Args:
            request: HTTP 请求对象。

        Returns:
            HTTP 响应对象。
        """
        match = self.check_referer(request)
        if not match:
            return HttpResponseForbidden('CSRF CHECK ERROR')
        response = self.get_response(request)
        return response
