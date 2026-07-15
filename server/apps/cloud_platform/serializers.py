"""云平台管理应用的序列化器。"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.cloud_platform import models
from apps.common.core.serializers import BaseModelSerializer, TabsColumn


class CloudPlatformSerializer(BaseModelSerializer):
    """云平台实例序列化器。"""

    class Meta:
        """序列化器元数据配置。"""

        model = models.CloudPlatform
        fields = [
            'pk',
            'name',
            'platform_type',
            'company',
            'endpoint',
            'region',
            'is_active',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'name',
            'platform_type',
            'company',
            'endpoint',
            'region',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': _('ID'),
                'help_text': _('主键唯一标识'),
            },
            'name': {
                'label': _('平台名称'),
                'help_text': _('自定义平台实例名称，如：生产环境-腾讯云'),
            },
            'platform_type': {
                'label': _('平台类型'),
                'help_text': _('云平台类型枚举：腾讯云/阿里云/AWS/Azure/华为云/vCenter/美橙/其他'),
            },
            'company': {
                'attrs': ['pk', 'name', 'short_name'],
                'required': False,
                'format': '{name}',
                'label': _('所属公司'),
                'help_text': _('平台归属的公司主体（个人注册或无公司归属可不填）'),
            },
            'endpoint': {
                'label': _('API 端点'),
                'help_text': _('API 访问地址，如 https://cvm.tencentcloudapi.com'),
            },
            'region': {
                'label': _('默认区域'),
                'help_text': _('默认区域标识，如 ap-guangzhou'),
            },
            'is_active': {
                'label': _('启用状态'),
                'help_text': _('平台是否启用，禁用后不可用于新建凭据'),
            },
            'description': {
                'label': _('Description'),
                'help_text': _('平台实例的描述说明'),
            },
            'created_time': {
                'read_only': True,
                'label': _('Created time'),
                'help_text': _('创建时间'),
            },
            'updated_time': {
                'read_only': True,
                'label': _('Updated time'),
                'help_text': _('更新时间'),
            },
        }


class CredentialListSerializer(BaseModelSerializer):
    """凭据列表序列化器（不包含敏感字段明文，仅用于列表展示）。"""

    platform_info = serializers.SerializerMethodField(
        read_only=True,
        label=_('所属平台'),
        help_text=_('凭据归属云平台的摘要信息'),
    )

    def get_platform_info(self, obj: models.Credential) -> dict:
        """获取所属平台的摘要信息。"""
        return {
            'pk': obj.platform.pk,
            'name': obj.platform.name,
            'platform_type': obj.platform.platform_type,
        }

    class Meta:
        """序列化器元数据配置。"""

        model = models.Credential
        fields = [
            'pk',
            'platform',
            'platform_info',
            'credential_type',
            'credential_name',
            'username',
            'email',
            'token_expire_time',
            'remark',
            'is_active',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'platform_info',
            'credential_type',
            'credential_name',
            'username',
            'email',
            'token_expire_time',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': _('ID'),
                'help_text': _('主键唯一标识'),
            },
            'platform': {
                'attrs': ['pk', 'name', 'platform_type'],
                'required': True,
                'format': '{name}({platform_type})',
                'label': _('所属平台'),
                'help_text': _('该凭据归属的云平台实例'),
            },
            'credential_type': {
                'label': _('凭据类型'),
                'help_text': _('凭据类型枚举：access_key/password/api_token'),
            },
            'credential_name': {
                'label': _('凭据名称'),
                'help_text': _('自定义凭据标识，如：运维账号'),
            },
            'username': {
                'label': _('用户名'),
                'help_text': _('登录用户名'),
            },
            'email': {
                'label': _('邮箱'),
                'help_text': _('关联邮箱（美橙等部分服务商认证需要）'),
            },
            'token_expire_time': {
                'label': _('Token 过期时间'),
                'help_text': _('Token 过期时间，为空表示永不过期'),
            },
            'remark': {
                'label': _('备注'),
                'help_text': _('凭据用途说明'),
            },
            'is_active': {
                'label': _('启用状态'),
                'help_text': _('凭据是否启用，禁用后不可用于API调用'),
            },
            'description': {
                'label': _('Description'),
                'help_text': _('凭据的描述说明'),
            },
            'created_time': {
                'read_only': True,
                'label': _('Created time'),
                'help_text': _('创建时间'),
            },
            'updated_time': {
                'read_only': True,
                'label': _('Updated time'),
                'help_text': _('更新时间'),
            },
        }


class CredentialDetailSerializer(BaseModelSerializer):
    """凭据详情序列化器（含加密字段，仅详情/编辑时使用）。"""

    class Meta:
        """序列化器元数据配置。"""

        model = models.Credential
        tabs = [
            TabsColumn(
                '基本信息',
                [
                    'platform',
                    'credential_type',
                    'credential_name',
                    'remark',
                    'is_active',
                    'description',
                    'token_expire_time',
                ],
            ),
            TabsColumn('Access Key', ['access_key', 'access_secret']),
            TabsColumn('用户名密码', ['username', 'password', 'email']),
            TabsColumn('API Token', ['api_token']),
            TabsColumn('扩展数据', ['extra_data']),
        ]
        fields = [
            'pk',
            'platform',
            'credential_type',
            'credential_name',
            'access_key',
            'access_secret',
            'username',
            'password',
            'email',
            'api_token',
            'token_expire_time',
            'extra_data',
            'remark',
            'is_active',
            'description',
            'created_time',
            'updated_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': _('ID'),
                'help_text': _('主键唯一标识'),
            },
            'platform': {
                'attrs': ['pk', 'name', 'platform_type'],
                'required': True,
                'format': '{name}({platform_type})',
                'label': _('所属平台'),
                'help_text': _('该凭据归属的云平台实例'),
            },
            'credential_type': {
                'label': _('凭据类型'),
                'help_text': _('凭据类型枚举：access_key/password/api_token'),
            },
            'credential_name': {
                'label': _('凭据名称'),
                'help_text': _('自定义凭据标识，如：运维账号'),
            },
            # 敏感字段仅 write_only，不在响应中暴露
            'access_key': {
                'write_only': True,
                'label': _('Access Key ID'),
                'help_text': _('云平台 Access Key ID（加密存储）'),
            },
            'access_secret': {
                'write_only': True,
                'label': _('Secret Access Key'),
                'help_text': _('云平台 Secret Access Key（加密存储）'),
            },
            'username': {
                'label': _('用户名'),
                'help_text': _('登录用户名'),
            },
            'password': {
                'write_only': True,
                'label': _('密码'),
                'help_text': _('登录密码（加密存储）'),
            },
            'email': {
                'label': _('邮箱'),
                'help_text': _('关联邮箱（美橙等部分服务商认证需要）'),
            },
            'api_token': {
                'write_only': True,
                'label': _('API Token'),
                'help_text': _('API 访问令牌（加密存储）'),
            },
            'token_expire_time': {
                'label': _('Token 过期时间'),
                'help_text': _('Token 过期时间，为空表示永不过期'),
            },
            'extra_data': {
                'label': _('扩展数据'),
                'help_text': _('扩展 JSON 字段，存储不同平台的个性化认证键值对'),
            },
            'remark': {
                'label': _('备注'),
                'help_text': _('凭据用途说明'),
            },
            'is_active': {
                'label': _('启用状态'),
                'help_text': _('凭据是否启用，禁用后不可用于API调用'),
            },
            'description': {
                'label': _('Description'),
                'help_text': _('凭据的描述说明'),
            },
            'created_time': {
                'read_only': True,
                'label': _('Created time'),
                'help_text': _('创建时间'),
            },
            'updated_time': {
                'read_only': True,
                'label': _('Updated time'),
                'help_text': _('更新时间'),
            },
        }
