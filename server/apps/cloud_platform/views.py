"""云平台管理应用的视图集。"""

from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.cloud_platform import models
from apps.cloud_platform.serializers import (
    CloudPlatformSerializer,
    CredentialDetailSerializer,
    CredentialListSerializer,
)
from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet
from apps.common.core.response import ApiResponse


class CloudPlatformFilter(BaseFilterSet):
    """云平台实例过滤器。"""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    platform_type = filters.CharFilter(field_name='platform_type', lookup_expr='exact')
    company = filters.CharFilter(field_name='company__pk', lookup_expr='exact')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = models.CloudPlatform
        fields = ['name', 'platform_type', 'company', 'is_active']


class CloudPlatformViewSet(BaseModelSet):
    """云平台实例管理"""

    queryset = models.CloudPlatform.objects.select_related('company').prefetch_related('credentials')
    serializer_class = CloudPlatformSerializer
    filterset_class = CloudPlatformFilter
    ordering_fields = ['created_time', 'name']


class CredentialFilter(BaseFilterSet):
    """凭据过滤器。"""

    platform = filters.CharFilter(field_name='platform__pk', lookup_expr='exact')
    credential_type = filters.CharFilter(field_name='credential_type', lookup_expr='exact')
    credential_name = filters.CharFilter(field_name='credential_name', lookup_expr='icontains')
    username = filters.CharFilter(field_name='username', lookup_expr='icontains')
    email = filters.CharFilter(field_name='email', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = models.Credential
        fields = ['platform', 'credential_type', 'credential_name', 'username', 'email', 'is_active']


class CredentialViewSet(BaseModelSet):
    """云平台凭据管理"""

    queryset = models.Credential.objects.select_related('platform')
    filterset_class = CredentialFilter
    ordering_fields = ['created_time', 'credential_name']

    def get_serializer_class(self):
        """根据 action 返回不同粒度的序列化器。

        - 列表接口使用 CredentialListSerializer（不泄露敏感信息）。
        - 详情/创建/更新使用 CredentialDetailSerializer（含加密字段）。
        """
        if self.action in ('list',):
            return CredentialListSerializer
        return CredentialDetailSerializer

    @action(methods=['post'], detail=True, url_path='decrypt')
    def decrypt_credential(self, request: Request, *args, **kwargs) -> Response:
        """解密凭据敏感字段，用于安全查看凭据明文。

        按凭据类型返回对应的敏感字段，同时返回扩展数据中可能存放的附加密钥。
        """
        instance = self.get_object()
        data: dict = {
            'pk': instance.pk,
            'credential_name': instance.credential_name,
            'credential_type': instance.credential_type,
        }

        cred_type = instance.credential_type
        if cred_type == models.Credential.CredentialTypeChoices.ACCESS_KEY:
            data['access_key'] = instance.access_key
            data['access_secret'] = instance.access_secret
        elif cred_type == models.Credential.CredentialTypeChoices.PASSWORD:
            data['username'] = instance.username
            data['password'] = instance.password
            if instance.email:
                data['email'] = instance.email
        elif cred_type == models.Credential.CredentialTypeChoices.API_TOKEN:
            data['api_token'] = instance.api_token
            data['token_expire_time'] = instance.token_expire_time

        if instance.extra_data:
            data['extra_data'] = instance.extra_data

        return ApiResponse(data=data, detail="凭据解密成功")
