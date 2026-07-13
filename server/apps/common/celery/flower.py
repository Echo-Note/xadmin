#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin_server
# filename : flower
# author : ly_13
# date : 6/29/2023
"""Celery Flower 监控代理视图。"""
import base64

from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_exempt
from drf_spectacular.utils import extend_schema
from proxy.views import proxy_view
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.utils import get_logger

logger = get_logger(__name__)

flower_url = f'{settings.CELERY_FLOWER_HOST}:{settings.CELERY_FLOWER_PORT}'


class CeleryFlowerAPIView(GenericAPIView):
    """celery 定时任务"""

    @extend_schema(exclude=True)
    @xframe_options_exempt
    def get(self, request: Request, path: str) -> Response:
        """获取 Flower 监控页面。"""
        remote_url = 'http://{}/api/flower/{}'.format(flower_url, path)
        try:
            basic_auth = base64.b64encode(settings.CELERY_FLOWER_AUTH.encode('utf-8')).decode('utf-8')
            response = proxy_view(request, remote_url, {
                'headers': {
                    'Authorization': f"Basic {basic_auth}"
                }
            })
        except Exception as e:
            logger.warning(f"celery flower service unavailable. {e}")
            msg = _("<h3>Celery flower service unavailable. Please contact the administrator</h3>")
            response = HttpResponse(msg)
        return response

    @extend_schema(exclude=True)
    @xframe_options_exempt
    def post(self, request: Request, path: str) -> Response:
        """操作 Flower 监控页面。"""
        return self.get(request, path)

