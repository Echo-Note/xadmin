#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin_server
# filename : request
# author : ly_13
# date : 6/27/2023
"""HTTP 请求相关工具模块，提供用户、IP、参数、浏览器等请求信息解析。"""

import base64
import json

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.utils.module_loading import import_string
from rest_framework.throttling import BaseThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
from user_agents import parse

from apps.common.core.auth import GetUserFromAccessToken


def get_request_user(request: HttpRequest) -> AbstractBaseUser:
    """获取请求关联的已认证用户，未认证时返回匿名用户。

    若请求中用户未认证，尝试通过 JWT 手动认证。

    Args:
        request: HTTP 请求对象。

    Returns:
        认证用户对象或匿名用户。
    """
    user: AbstractBaseUser = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user
    try:
        user, token = JWTAuthentication().authenticate(request)
    except Exception as e:
        try:
            body = getattr(request, 'request_data', {})
            refresh_token = body.get('refresh')
            if refresh_token:
                token = GetUserFromAccessToken(refresh_token)
                auth_class = import_string(settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES')[0])()
                user = auth_class.get_user(token)
        except Exception as e:
            pass
    return user or AnonymousUser()


def get_request_ip(request: HttpRequest) -> str:
    """从请求中获取客户端真实 IP 地址。

    优先解析 X-Forwarded-For 头，其次使用 REMOTE_ADDR。

    Args:
        request: HTTP 请求对象。

    Returns:
        客户端 IP 地址字符串。
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')
    if x_forwarded_for and x_forwarded_for[0]:
        login_ip = x_forwarded_for[0]
        if login_ip.count(':') == 1:
            # format: ipv4:port (非标准格式的 X-Forwarded-For)
            return login_ip.split(':')[0]
        return login_ip
    ip = request.META.get('REMOTE_ADDR', '') or getattr(request, 'request_ip', None)
    return ip or 'unknown'


def get_request_data(request: HttpRequest) -> dict:
    """获取请求参数，合并 GET、POST 与 body 数据。

    Args:
        request: HTTP 请求对象。

    Returns:
        包含请求参数的字典。
    """
    request_data = getattr(request, 'request_data', None)
    if request_data:
        return request_data
    if request.META.get('CONTENT_TYPE', '').startswith('multipart/'):
        # 避免字段检查直接报错，axios中form-data数据字段和json字段不统一
        return 'multipart/form-data'
    data: dict = {**request.GET.dict(), **request.POST.dict()}
    if not data:
        try:
            body = request.body
            if body:
                data = json.loads(body)
        except Exception as e:
            pass
        if not isinstance(data, dict):
            data = {'data': data}
    return data


def get_request_path(request: HttpRequest, *args, **kwargs) -> str:
    """获取请求路径，并将路径参数替换为占位符。

    Args:
        request: HTTP 请求对象。
        *args: 需要在路径中替换的参数值。
        **kwargs: 额外参数（未使用）。

    Returns:
        处理后的请求路径字符串。
    """
    request_path = getattr(request, 'request_path', None)
    if request_path:
        return request_path
    values = []
    for arg in args:
        if len(arg) == 0:
            continue
        if isinstance(arg, str):
            values.append(arg)
        elif isinstance(arg, (tuple, set, list)):
            values.extend(arg)
        elif isinstance(arg, dict):
            values.extend(arg.values())
    if len(values) == 0:
        return request.path
    path: str = request.path
    for value in values:
        path = path.replace('/' + value, '/' + '{id}')
    return path


def get_browser(request: HttpRequest) -> str:
    """从请求 User-Agent 中解析浏览器名称。

    Args:
        request: HTTP 请求对象。

    Returns:
        浏览器名称字符串。
    """
    ua_string = request.META['HTTP_USER_AGENT']
    user_agent = parse(ua_string)
    return user_agent.get_browser()


def get_os(request: HttpRequest) -> str:
    """从请求 User-Agent 中解析操作系统名称。

    Args:
        request: HTTP 请求对象。

    Returns:
        操作系统名称字符串。
    """
    ua_string = request.META['HTTP_USER_AGENT']
    user_agent = parse(ua_string)
    return user_agent.get_os()


def get_verbose_name(queryset: object | None = None, view: object | None = None, model: type | None = None) -> tuple:
    """获取模型或视图的 verbose_name。

    Args:
        queryset: 可选的查询集，用于推断模型。
        view: 可选的视图对象，用于推断模型或获取文档字符串。
        model: 可选的模型类。

    Returns:
        元组 (model, verbose_name)。
    """
    verbose_name = ''
    try:
        if view is not None and hasattr(view, '__doc__'):
            verbose_name = getattr(view, '__doc__')
        if queryset is not None and hasattr(queryset, 'model'):
            model = queryset.model
        elif view and hasattr(view.get_queryset(), 'model'):
            model = view.get_queryset().model
        elif view and hasattr(view.get_serializer(), 'Meta') and hasattr(view.get_serializer().Meta, 'model'):
            model = view.get_serializer().Meta.model
        if model and not verbose_name:
            verbose_name = getattr(model, '_meta').verbose_name
    except Exception as e:
        pass
    return model, verbose_name


def get_request_ident(request: HttpRequest) -> str:
    """生成请求唯一标识，基于 User-Agent、Accept 与远端地址。

    Args:
        request: HTTP 请求对象。

    Returns:
        Base64 编码的请求标识字符串。
    """
    http_user_agent = request.META.get('HTTP_USER_AGENT')
    http_accept = request.META.get('HTTP_ACCEPT')
    remote_addr = BaseThrottle().get_ident(request)
    return base64.b64encode(f'{http_user_agent}{http_accept}{remote_addr}'.encode('utf-8')).decode('utf-8')
