#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : system
# author : ly_13
# date : 6/2/2023
"""认证与鉴权核心模块，提供认证装饰器、自定义 JWT Token 及 Cookie 认证支持。"""

import functools
import hashlib
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest
from django.http.cookie import parse_cookie
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.common.cache.storage import BlackAccessTokenCache


def auth_required(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """视图认证装饰器，校验请求用户是否已认证。

    Args:
        view_func: 被装饰的视图函数。

    Returns:
        包装后的视图函数，未认证时抛出 ``NotAuthenticated`` 异常。
    """

    @functools.wraps(view_func)
    def wrapper(view: Any, request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        if request.user and request.user.is_authenticated:
            return view_func(view, request, *args, **kwargs)
        raise NotAuthenticated(_('Unauthorized authentication'))

    return wrapper


class ServerAccessToken(AccessToken):
    """
    自定义的token方法是为了登出的时候，将 access token 禁用
    """

    def verify(self) -> None:
        """校验 token 有效性，若 token 已被加入黑名单则抛出 ``TokenError``。"""
        user_id = self.payload.get('user_id')
        if BlackAccessTokenCache(user_id, hashlib.md5(self.token).hexdigest()).get_storage_cache():
            raise TokenError(_('Token is invalid or expired'))
        super().verify()


class GetUserFromAccessToken(AccessToken):
    """从 access token 中获取用户的 token 类，复用 refresh token 类型。"""

    token_type = 'refresh'


class CookieJWTAuthentication(JWTAuthentication):
    """
    支持cookie认证，是为了可以访问 django-proxy 的页面，比如 flower
    """

    def get_header(self, request: HttpRequest) -> bytes:
        """获取认证头信息，优先从请求头获取，不存在时回退到 Cookie 中的 X-Token。

        Args:
            request: HTTP 请求对象。

        Returns:
            认证头字节数据，不存在时返回父类结果。
        """
        header = super().get_header(request)
        if not header:
            cookies = request.META.get('HTTP_COOKIE')
            if cookies:
                cookie_dict = parse_cookie(cookies)
                if cookie_dict and cookie_dict.get('X-Token'):
                    header = f'Bearer {cookie_dict.get("X-Token")}'.encode('utf-8')
        return header
