"""云平台管理应用的序列化器。"""

from rest_framework import serializers

from apps.cloud_platform import models
from apps.common.core.serializers import BaseModelSerializer, TabsColumn


class CloudPlatformSerializer(BaseModelSerializer):
    """云平台实例序列化器。"""

    class Meta:
        model = models.CloudPlatform
        fields = [
            'pk', 'name', 'platform_type', 'company',
            'endpoint', 'region', 'is_active',
            'description', 'created_time', 'updated_time',
        ]
        table_fields = [
            'pk', 'name', 'platform_type', 'company',
            'endpoint', 'region', 'is_active', 'created_time',
        ]
        extra_kwargs = {
            'pk': {'read_only': True},
            'company': {
                'attrs': ['pk', 'name', 'short_name'],
                'required': False,
                'format': "{name}",
            },
        }


class CredentialListSerializer(BaseModelSerializer):
    """凭据列表序列化器（不包含敏感字段明文，仅用于列表展示）。"""

    platform_info = serializers.SerializerMethodField(read_only=True, label="所属平台")

    def get_platform_info(self, obj: models.Credential) -> dict:
        """获取所属平台的摘要信息。"""
        return {
            'pk': obj.platform.pk,
            'name': obj.platform.name,
            'platform_type': obj.platform.platform_type,
        }

    class Meta:
        model = models.Credential
        fields = [
            'pk', 'platform', 'platform_info', 'credential_type',
            'credential_name', 'username', 'email',
            'token_expire_time', 'remark', 'is_active',
            'description', 'created_time', 'updated_time',
        ]
        table_fields = [
            'pk', 'platform_info', 'credential_type', 'credential_name',
            'username', 'email', 'token_expire_time', 'is_active', 'created_time',
        ]
        extra_kwargs = {
            'pk': {'read_only': True},
            'platform': {
                'attrs': ['pk', 'name', 'platform_type'],
                'required': True,
                'format': "{name}({platform_type})",
            },
        }


class CredentialDetailSerializer(BaseModelSerializer):
    """凭据详情序列化器（含加密字段，仅详情/编辑时使用）。"""

    class Meta:
        model = models.Credential
        tabs = [
            TabsColumn('基本信息', [
                'platform', 'credential_type', 'credential_name',
                'remark', 'is_active', 'description', 'token_expire_time',
            ]),
            TabsColumn('Access Key', ['access_key', 'access_secret']),
            TabsColumn('用户名密码', ['username', 'password', 'email']),
            TabsColumn('API Token', ['api_token']),
            TabsColumn('扩展数据', ['extra_data']),
        ]
        fields = [
            'pk', 'platform', 'credential_type', 'credential_name',
            'access_key', 'access_secret', 'username', 'password', 'email',
            'api_token', 'token_expire_time',
            'extra_data', 'remark', 'is_active', 'description',
            'created_time', 'updated_time',
        ]
        extra_kwargs = {
            'pk': {'read_only': True},
            'platform': {
                'attrs': ['pk', 'name', 'platform_type'],
                'required': True,
                'format': "{name}({platform_type})",
            },
            # 敏感字段仅 write_only，不在响应中暴露
            'access_key': {'write_only': True},
            'access_secret': {'write_only': True},
            'password': {'write_only': True},
            'api_token': {'write_only': True},
        }
