#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin_server
# filename : middleware
# author : ly_13
# date : 6/27/2023
"""API 日志中间件，记录请求响应信息及操作日志。"""

import json
import time
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework.utils import encoders

from apps.common.utils import get_logger
from apps.common.utils.request import get_request_user, get_request_ip, get_request_data, get_os, \
    get_browser, get_verbose_name
from apps.system.models import OperationLog

logger = get_logger(__name__)


class ApiLoggingMiddleware(MiddlewareMixin):
    """API 操作日志中间件，记录请求开始/结束信息并持久化操作日志。"""

    def __init__(self, get_response: Any = None) -> None:
        """初始化中间件，读取日志相关配置。

        Args:
            get_response: Django 请求处理链中的下一个回调。
        """
        super().__init__(get_response)
        self.enable = getattr(settings, 'API_LOG_ENABLE', None) or False
        self.methods = getattr(settings, 'API_LOG_METHODS', None) or set()
        self.ignores = getattr(settings, 'API_LOG_IGNORE', None) or {}
        self.operation_log_id = '__operation_log_id'

    @classmethod
    def __handle_request(cls, request: HttpRequest) -> None:
        """处理请求开始阶段，记录请求 IP、请求数据及开始时间。

        Args:
            request: HTTP 请求对象。
        """
        request.request_ip = get_request_ip(request)
        request.request_data = get_request_data(request)
        request.request_start_time = time.time()
        logger.debug(f"request start. {request.method} {request.path} {getattr(request, 'request_data', {})}")

    def __handle_response(self, request: HttpRequest, response: HttpResponse) -> bool:
        """处理响应阶段，计算执行耗时并更新操作日志记录。

        Args:
            request: HTTP 请求对象。
            response: HTTP 响应对象。

        Returns:
            是否成功记录操作日志。
        """
        request_start_time = getattr(request, 'request_start_time', None)
        exec_time = time.time() - request_start_time
        if exec_time > 1:
            logger.warning(
                f"exec time {exec_time} over 1s. {request.method} {request.path} {getattr(request, 'request_data', {})}")
        # 判断有无log_id属性，使用All记录时，会出现此情况
        operation_log_id = getattr(request, self.operation_log_id, None)
        if operation_log_id is None:
            return False

        body = getattr(request, 'request_data', {})
        # 请求含有password则用*替换掉(暂时先用于所有接口的password请求参数)
        if isinstance(body, dict) and body.get('password', ''):
            body['password'] = '*' * len(body['password'])
        if not hasattr(response, 'data') or not isinstance(response.data, dict):
            response.data = {}
        try:
            if not response.data and response.content:
                content = json.loads(response.content.decode().replace('\\', ''))
                response.data = content if isinstance(content, dict) else {}
        except Exception:
            return False
        user = get_request_user(request)
        request_module = getattr(request, 'request_module', '')
        if hasattr(response, 'renderer_context'):
            action_doc = getattr(response.renderer_context['view'], request.method.lower()).__doc__
            if action_doc:
                try:
                    action_doc = action_doc.format(cls=request_module)
                except Exception:
                    action_doc = request_module
            else:
                action_doc = request_module
        else:
            action_doc = request_module
        info = {
            'module': action_doc,
            'creator': user if not isinstance(user, AnonymousUser) else None,
            'dept_belong_id': getattr(request.user, 'dept_id', None),
            'ipaddress': getattr(request, 'request_ip'),
            'method': request.method,
            'path': request.path,
            'body': json.dumps(body) if isinstance(body, dict) else body,
            'response_code': response.status_code,
            'system': get_os(request),
            'browser': get_browser(request),
            'status_code': response.data.get('code'),
            'request_uuid': getattr(request, 'request_uuid', None),
            'exec_time': time.time() - request_start_time,
            'response_result': json.dumps({"code": response.data.get('code'), "data": response.data.get('data'),
                                           "detail": response.data.get('detail')}, cls=encoders.JSONEncoder),
        }
        try:
            OperationLog.objects.update_or_create(defaults=info, id=operation_log_id)
        except Exception:  # sqlite3 数据库因为锁表可能会导致日志记录失败
            pass
        del info['request_uuid']
        logger.debug(f"request end. {request.method} {request.path} {getattr(request, 'request_data', {})} log:{info}")
        return True

    def process_view(self, request: HttpRequest, view_func: Any, view_args: list, view_kwargs: dict) -> None:
        """在视图执行前判断是否需要记录操作日志，并预创建日志记录。

        Args:
            request: HTTP 请求对象。
            view_func: 即将执行的视图函数。
            view_args: 位置参数列表。
            view_kwargs: 关键字参数字典。
        """
        if hasattr(view_func, 'cls') and hasattr(view_func.cls, 'queryset'):
            if self.enable:
                if self.methods == 'ALL' or request.method in self.methods:
                    model, v = get_verbose_name(view_func.cls.queryset, view_func.cls)
                    if (model and request.method in self.ignores.get(model._meta.label, [])) or (
                            request.method in self.ignores.get(request.path, [])):
                        return
                    if not v:
                        v = settings.API_MODEL_MAP.get(request.path, v)
                        if not v and model:
                            v = model._meta.label
                    log = OperationLog(module=v)
                    log.save()
                    setattr(request, self.operation_log_id, log.id)
                    setattr(request, 'request_module', v)

        return

    def process_request(self, request: HttpRequest) -> None:
        """请求预处理，记录请求信息（健康检查接口除外）。

        Args:
            request: HTTP 请求对象。
        """
        if request.path == '/api/common/api/health':
            return
        self.__handle_request(request)

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """响应后处理，记录响应信息及操作日志（健康检查接口除外）。

        Args:
            request: HTTP 请求对象。
            response: HTTP 响应对象。

        Returns:
            传入的响应对象。
        """
        if request.path == '/api/common/api/health':
            return response
        show = False
        if self.enable:
            if self.methods == 'ALL' or request.method in self.methods:
                show = self.__handle_response(request, response)
        if not show:
            logger.debug(f" request end. {request.method} {request.path} {getattr(response, 'data', {})}")
        return response
