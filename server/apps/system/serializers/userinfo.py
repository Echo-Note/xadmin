"""用户个人信息序列化器。"""


from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.base.utils import AESCipherV2
from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.settings.utils.password import check_password_rules
from apps.system import models
from apps.system.models import UserInfo

logger = get_logger(__name__)


class UserInfoSerializer(BaseModelSerializer):
    """用户个人信息序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserInfo
        write_fields = ['username', 'nickname', 'gender']
        fields = write_fields + ['email', 'last_login', 'pk', 'phone', 'avatar', 'roles', 'date_joined', 'dept']
        read_only_fields = list(set([x.name for x in models.UserInfo._meta.fields]) - set(write_fields))
        extra_kwargs = {
            'username': {'label': _('Username'), 'help_text': _('Unique username for login')},
            'nickname': {'label': _('Nickname'), 'help_text': _('Display name of the user')},
            'gender': {'label': _('Gender'), 'help_text': _('Gender of the user')},
            'email': {'label': _('Email'), 'help_text': _('Email address of the user')},
            'last_login': {'label': _('Last login'), 'help_text': _('Time of the last successful login')},
            'phone': {'label': _('Phone'), 'help_text': _('Phone number of the user')},
            'avatar': {'label': _('Avatar'), 'help_text': _('Avatar image of the user')},
            'date_joined': {'label': _('Date joined'), 'help_text': _('Time when the user account was created')},
        }

    dept = serializers.CharField(source='dept.name', read_only=True, label=_('Department'),
                                 help_text=_('Name of the department the user belongs to'))
    roles = serializers.SerializerMethodField(label=_('Role permission'),
                                              help_text=_('List of role names assigned to the user'))

    @extend_schema_field(serializers.ListField)
    def get_roles(self, obj: UserInfo) -> list[str]:
        """获取用户的角色名称列表。

        Args:
            obj: UserInfo 模型实例。

        Returns:
            角色名称列表。
        """
        return list(obj.roles.values_list('name', flat=True))


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器。"""

    old_password = serializers.CharField(
        min_length=5, max_length=128, required=True, write_only=True, label=_('Old password'),
        help_text=_('Current password of the user, used for verification before changing')
    )
    sure_password = serializers.CharField(
        min_length=5, max_length=128, required=True, write_only=True, label=_('Confirm password'),
        help_text=_('New password to set, must match the confirmation')
    )

    def update(self, instance: UserInfo, validated_data: dict) -> UserInfo:
        """验证旧密码并设置新密码。

        Args:
            instance: 待更新的 UserInfo 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 UserInfo 实例。
        """
        sure_password = AESCipherV2(instance.username).decrypt(validated_data.get('sure_password'))
        old_password = AESCipherV2(instance.username).decrypt(validated_data.get('old_password'))
        if not instance.check_password(old_password):
            raise serializers.ValidationError(_('Old password verification failed'))
        if not check_password_rules(sure_password, instance.is_superuser):
            raise serializers.ValidationError(_('Password does not match security rules'))

        instance.set_password(sure_password)
        instance.modifier = self.context.get('request').user
        instance.save(update_fields=['password', 'modifier'])
        return instance
