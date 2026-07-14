"""系统配置序列化器。"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.core.config import SysConfig, UserConfig
from apps.common.core.fields import BasePrimaryKeyRelatedField
from apps.common.core.serializers import BaseModelSerializer
from apps.common.fields.utils import input_wrapper
from apps.common.utils import get_logger
from apps.system.models import SystemConfig, UserPersonalConfig, UserInfo

logger = get_logger(__name__)


class SystemConfigSerializer(BaseModelSerializer):
    """系统配置序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = SystemConfig
        fields = ['pk', 'key', 'value', 'cache_value', 'is_active', 'inherit', 'access', 'description', 'created_time']
        read_only_fields = ['pk']
        fields_unexport = ['cache_value']  # 导入导出文件时，忽略该字段
        extra_kwargs = {
            'key': {'label': _('Config name'), 'help_text': _('Unique configuration key name')},
            'value': {'label': _('Config value'), 'help_text':_('Configuration value stored in JSON format')},
            'is_active': {'label': _('Is active'), 'help_text': _('Whether this configuration is enabled')},
            'inherit': {'label': _('User inherit'),
                        'help_text': _('Allows users to inherit this config')},
            'access': {'label': _('API access'),
                       'help_text': _('Allows API interfaces to access this config')},
            'description': {'label': _('Description'), 'help_text': _('Description of this configuration')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
        }

    cache_value = input_wrapper(serializers.SerializerMethodField)(read_only=True, label=_('Config cache value'),
                                                                   help_text=_('Cached configuration value'),
                                                                   input_type='json')

    @extend_schema_field(serializers.JSONField)
    def get_cache_value(self, obj: SystemConfig) -> dict:
        """获取系统配置的缓存值。

        Args:
            obj: SystemConfig 模型实例。

        Returns:
            配置的缓存值。
        """
        return SysConfig.get_value(obj.key)


class UserPersonalConfigExportImportSerializer(SystemConfigSerializer):
    """用户个人配置导入导出序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserPersonalConfig
        fields = ['pk', 'value', 'key', 'is_active', 'created_time', 'description', 'cache_value', 'owner', 'access']
        read_only_fields = ['pk']
        extra_kwargs = {'owner': {'attrs': ['pk', 'username'], 'required': True,
                                  'label': _('User'), 'help_text': _('User to whom this personal config belongs')}}


class UserPersonalConfigSerializer(SystemConfigSerializer):
    """用户个人配置序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserPersonalConfig
        fields = [
            'pk', 'config_user', 'owner', 'key', 'value', 'cache_value', 'is_active', 'access', 'description',
            'created_time'
        ]
        read_only_fields = ['pk', 'owner']
        extra_kwargs = {'owner': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}',
                                  'label': _('User'), 'help_text': _('User to whom this personal config belongs')},
                        'key': {'label': _('Config name'), 'help_text': _('Configuration key name')},
                        'value': {'label': _('Config value'), 'help_text': _('Configuration value stored in JSON format')},
                        'is_active': {'label': _('Is active'), 'help_text': _('Whether this configuration is enabled')},
                        'access': {'label': _('API access'),
                                   'help_text': _('Allows API interfaces to access this config')},
                        'description': {'label': _('Description'),
                                        'help_text': _('Description of this configuration')},
                        'created_time': {'label': _('Created time'),
                                         'help_text': _('Time when this record was created')}}

    config_user = BasePrimaryKeyRelatedField(write_only=True, many=True, queryset=UserInfo.objects,
                                             label=_('Users'), help_text=_('Users for whom this config will be created'),
                                             input_type='api-search-user')

    def create(self, validated_data: dict) -> UserPersonalConfig:
        """为指定用户创建个人配置。

        Args:
            validated_data: 已验证的数据字典。

        Returns:
            最后创建的 UserPersonalConfig 实例。
        """
        config_user = validated_data.pop('config_user', [])
        owner = validated_data.pop('owner', None)
        instance = None
        if not config_user and not owner:
            raise ValidationError(_('User cannot be null'))
        if owner:
            config_user.append(owner)
        for owner in config_user:
            validated_data['owner'] = owner
            instance = super().create(validated_data)
        return instance

    def update(self, instance: UserPersonalConfig, validated_data: dict) -> UserPersonalConfig:
        """更新用户个人配置，忽略 config_user 字段。

        Args:
            instance: 待更新的 UserPersonalConfig 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 UserPersonalConfig 实例。
        """
        validated_data.pop('config_user', None)
        return super().update(instance, validated_data)

    @extend_schema_field(serializers.JSONField)
    def get_cache_value(self, obj: UserPersonalConfig) -> dict:
        """获取用户个人配置的缓存值。

        Args:
            obj: UserPersonalConfig 模型实例。

        Returns:
            配置的缓存值。
        """
        return UserConfig(obj.owner).get_value(obj.key)
