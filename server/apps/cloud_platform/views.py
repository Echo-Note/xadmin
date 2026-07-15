"""云平台管理应用的视图集。"""

from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.cloud_platform.choices import CredentialTypeChoices
from apps.cloud_platform.filters import CloudPlatformFilter, CredentialFilter
from apps.cloud_platform.models import CloudPlatform, Credential
from apps.cloud_platform.serializers import (
    CloudPlatformSerializer,
    CredentialDetailSerializer,
    CredentialListSerializer,
)
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.response import ApiResponse


class CloudPlatformViewSet(BaseModelSet, ImportExportDataAction):
    """云平台实例管理，支持导入导出。"""

    queryset = CloudPlatform.objects.select_related('company').prefetch_related('credentials')
    serializer_class = CloudPlatformSerializer
    filterset_class = CloudPlatformFilter
    ordering_fields = ['created_time', 'name']


class CredentialViewSet(BaseModelSet, ImportExportDataAction):
    """云平台凭据管理，支持导入导出（敏感字段仅导入模板可见）。"""

    queryset = Credential.objects.select_related('platform')
    filterset_class = CredentialFilter
    ordering_fields = ['created_time', 'credential_name']

    def get_serializer_class(self) -> type:
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
        if cred_type == CredentialTypeChoices.ACCESS_KEY:
            data['access_key'] = instance.access_key
            data['access_secret'] = instance.access_secret
        elif cred_type == CredentialTypeChoices.PASSWORD:
            data['username'] = instance.username
            data['password'] = instance.password
            if instance.email:
                data['email'] = instance.email
        elif cred_type == CredentialTypeChoices.API_TOKEN:
            data['api_token'] = instance.api_token
            data['token_expire_time'] = instance.token_expire_time

        if instance.extra_data:
            data['extra_data'] = instance.extra_data

        return ApiResponse(data=data, detail='凭据解密成功')
