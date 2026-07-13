#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : views
# author : ly_13
# date : 8/12/2024
"""接口文档 Swagger/Redoc 视图。"""

from collections.abc import Callable

from django.contrib.auth import login, logout
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_exempt
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import (
    SpectacularSwaggerView, SpectacularRedocView,
    SpectacularYAMLAPIView, SpectacularJSONAPIView
)
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainSerializer

from apps.common.base.magic import cache_response
from apps.common.core.response import ApiResponse


class ApiLogin(GenericAPIView):
    """接口文档的登录接口"""
    permission_classes = ()
    serializer_class = TokenObtainSerializer

    @extend_schema(exclude=True)
    @xframe_options_exempt
    def post(self, request: Request, *args, **kwargs) -> Response:
        """处理接口文档登录请求。"""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            login(request, serializer.user)
        except Exception as e:
            return ApiResponse(detail=_("Incorrect username/password"))
        response = redirect(request.query_params.get("next", "/api-docs/swagger/"))
        return response

    @extend_schema(exclude=True)
    @xframe_options_exempt
    def get(self, request: Request, *args, **kwargs) -> Response:
        """返回登录页面或重定向到文档。"""
        if request.user.is_authenticated:
            return redirect(to="/api-docs/swagger/")
        return ApiResponse(detail=_("Please enter your account information to log in"))


class ApiLogout(GenericAPIView):
    """接口文档的登出接口。"""

    permission_classes = []

    @extend_schema(exclude=True)
    @xframe_options_exempt
    def get(self, request: Request, *args, **kwargs) -> Response:
        """处理接口文档登出请求。"""
        logout(request)
        return redirect("/api-docs/login/")


class SchemaMixin:
    """接口文档 schema 视图混入类，提供缓存能力。"""

    @xframe_options_exempt
    @cache_response(timeout=60 * 5, key_func='get_cache_key')
    def get(self, *args, **kwargs) -> Response:
        """获取 schema 响应并缓存。"""
        return super().get(*args, **kwargs)

    def get_cache_key(
        self, view_instance: GenericAPIView, view_method: Callable, request: Request, args: tuple, kwargs: dict
    ) -> str:
        """生成 schema 视图的缓存键。

        Args:
            view_instance: 视图实例。
            view_method: 视图方法。
            request: HTTP 请求对象。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            缓存键字符串。
        """
        func_name = f'{view_instance.__class__.__name__}_{view_method.__name__}'
        return f"{func_name}_{request.user.pk}"


@extend_schema(exclude=True)
class JsonApi(SchemaMixin, SpectacularJSONAPIView):
    """JSON 格式的 OpenAPI schema 视图。"""


@extend_schema(exclude=True)
class YamlApi(SchemaMixin, SpectacularYAMLAPIView):
    """YAML 格式的 OpenAPI schema 视图。"""


@extend_schema(exclude=True)
class SwaggerUI(SchemaMixin, SpectacularSwaggerView):
    """Swagger UI 视图。"""


@extend_schema(exclude=True)
class Redoc(SchemaMixin, SpectacularRedocView):
    """Redoc 文档视图。"""

