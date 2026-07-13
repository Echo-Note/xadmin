#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : sms
# author : ly_13
# date : 8/6/2024
"""短信服务设置视图集定义。"""

import importlib

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from drf_spectacular.plumbing import build_array_type, build_object_type, build_basic_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.base.utils import get_choices_dict
from apps.common.core.response import ApiResponse
from apps.common.sdk.sms.endpoint import BACKENDS
from apps.common.swagger.utils import get_default_response_schema
from apps.common.utils import get_logger
from apps.settings.models import Setting
from apps.settings.serializers.sms import AlibabaSMSSettingSerializer, SMSSettingSerializer
from apps.settings.views.settings import BaseSettingViewSet

logger = get_logger(__name__)


class SmsSettingViewSet(BaseSettingViewSet):
    """短信配置设置视图集。"""

    serializer_class = SMSSettingSerializer
    category = "sms"

    @extend_schema(parameters=None, responses=get_default_response_schema(
        {
            'data': build_array_type(build_object_type(
                properties={
                    'value': build_basic_type(OpenApiTypes.STR),
                    'label': build_basic_type(OpenApiTypes.STR),
                }
            ))
        }
    ))
    @action(methods=['get'], detail=False)
    def backends(self, request: Request, *args, **kwargs) -> Response:
        """获取可配置短信后端。"""
        return ApiResponse(data=get_choices_dict(BACKENDS.choices))


class SmsConfigViewSet(BaseSettingViewSet):
    """短信服务配置视图集。"""

    serializer_class_mapper = {
        'alibaba': AlibabaSMSSettingSerializer,
    }

    @property
    def test_code(self) -> str:
        """返回测试验证码。"""
        return '6' * settings.VERIFY_CODE_LENGTH

    @staticmethod
    def get_or_from_setting(key: str, value: str = '') -> str:
        """从数据库设置中获取值，若传入值非空则直接返回。

        Args:
            key: 设置项名称。
            value: 传入值。

        Returns:
            设置值或空字符串。
        """
        if not value:
            secret = Setting.objects.filter(name=key).first()
            if secret:
                value = secret.cleaned_value

        return value or ''

    def get_alibaba_params(self, data: dict) -> tuple:
        """构建阿里云短信的初始化与发送参数。

        Args:
            data: 包含阿里云配置的字典。

        Returns:
            tuple: (初始化参数, 发送短信参数)。
        """
        init_params = {
            'access_key_id': data['ALIBABA_ACCESS_KEY_ID'],
            'access_key_secret': self.get_or_from_setting(
                'ALIBABA_ACCESS_KEY_SECRET', data.get('ALIBABA_ACCESS_KEY_SECRET')
            )
        }
        send_sms_params = {
            'sign_name': data['ALIBABA_VERIFY_SIGN_NAME'],
            'template_code': data['ALIBABA_VERIFY_TEMPLATE_CODE'],
            'template_param': {'code': self.test_code}
        }
        return init_params, send_sms_params

    def get_params_by_backend(self, backend: str, data: dict) -> tuple:
        """根据后端类型返回对应的参数。

        Args:
            backend: 后端名称。
            data: 配置数据。

        Returns:
            tuple: (初始化参数, 发送短信参数)。
        """
        get_params_func = getattr(self, 'get_%s_params' % backend)
        return get_params_func(data)

    def create(self, request: Request, *args, **kwargs) -> Response:
        """测试短信服务连通性。"""
        serializer = self.get_serializer_class()(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_phone = serializer.validated_data.get('SMS_TEST_PHONE')
        if not test_phone:
            return ApiResponse(code=1001, detail=_('test_phone is required'))

        init_params, send_sms_params = self.get_params_by_backend(self.category, serializer.validated_data)
        m = importlib.import_module(f'common.sdk.sms.{self.category}', __package__)
        try:
            client = m.client(**init_params)
            client.send_sms(
                phone_numbers=[test_phone],
                **send_sms_params
            )
            status_code = status.HTTP_200_OK
            detail = _('Test success')
        except APIException as e:
            try:
                error = e.detail['errmsg']
            except:
                error = e.detail
            status_code = status.HTTP_400_BAD_REQUEST
            detail = error
        except Exception as e:
            status_code = status.HTTP_400_BAD_REQUEST
            detail = str(e)
        return ApiResponse(code=status_code, detail=detail)
