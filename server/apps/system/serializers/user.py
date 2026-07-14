"""用户序列化器。"""

from django.contrib.auth.hashers import make_password
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from apps.common.base.utils import AESCipherV2
from apps.common.core.serializers import BaseModelSerializer
from apps.common.fields.utils import input_wrapper
from apps.common.utils import get_logger
from apps.message.utils import get_online_user_layers
from apps.settings.utils.password import check_password_rules
from apps.settings.utils.security import LoginBlockUtil
from apps.system.models import UserInfo

logger = get_logger(__name__)


class UserSerializer(BaseModelSerializer):
    """用户序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserInfo
        fields = [
            'pk', 'avatar', 'username', 'nickname', 'phone', 'email', 'gender', 'block', 'online_count', 'is_active',
            'password', 'dept', 'description', 'last_login', 'date_joined', 'roles', 'rules', 'mode_type'
        ]
        read_only_fields = ['pk'] + list(set([x.name for x in UserInfo._meta.fields]) - set(fields))
        table_fields = [
            'pk', 'avatar', 'username', 'nickname', 'gender', 'block', 'online_count', 'is_active', 'dept', 'phone',
            'last_login', 'date_joined', 'roles', 'rules'
        ]
        extra_kwargs = {
            'pk': {'read_only': True, 'label': _('ID'), 'help_text': _('Primary key ID')},
            'last_login': {'read_only': True, 'label': _('Last login'), 'help_text': _('Last login time of the user')},
            'date_joined': {'read_only': True, 'label': _('Date joined'),
                            'help_text': _('Date and time when the user account was created')},
            'avatar': {'read_only': True, 'label': _('Avatar'), 'help_text': _('User avatar image')},
            'password': {'write_only': True, 'label': _('Password'),
                         'help_text': _('Encrypted password for the user account')},
            'roles': {'required': False, 'attrs': ['pk', 'name', 'code'], 'format': '{name}', 'many': True,
                       'label': _('Role permission'), 'help_text': _('Roles assigned to the user')},
            'rules': {'required': False, 'attrs': ['pk', 'name', 'get_mode_type_display'], 'format': '{name}',
                      'many': True, 'label': _('Data permission'),
                      'help_text': _('Data permission rules assigned to the user')},
            'dept': {'required': False, 'attrs': ['pk', 'name', 'parent_id'], 'format': '{name}',
                     'label': _('Department'), 'help_text': _('Department to which the user belongs')},
            'email': {'validators': [UniqueValidator(queryset=UserInfo.objects.all())],
                      'label': _('Email'), 'help_text': _('Email address of the user')},
            'phone': {'validators': [UniqueValidator(queryset=UserInfo.objects.all())],
                      'label': _('Phone'), 'help_text': _('Phone number of the user')},
            'username': {'label': _('Username'), 'help_text': _('Unique username for login')},
            'nickname': {'label': _('Nickname'), 'help_text': _('Display name of the user')},
            'gender': {'label': _('Gender'), 'help_text': _('Gender of the user')},
            'is_active': {'label': _('Is active'), 'help_text': _('Whether the user account is active')},
            'description': {'label': _('Description'), 'help_text': _('Description of the user')},
            'mode_type': {'label': _('Data permission mode'),
                          'help_text': _('Permission mode, AND means all rules must be satisfied, OR means any rule')},
        }

    block = input_wrapper(serializers.SerializerMethodField)(read_only=True, input_type='boolean',
                                                             label=_('Login blocked'),
                                                             help_text=_('Whether the user is blocked from login'))
    online_count = input_wrapper(serializers.SerializerMethodField)(read_only=True, input_type='number',
                                                                    label=_('Online count'),
                                                                    help_text=_('Number of active online sessions of the user'))

    @extend_schema_field(serializers.BooleanField)
    def get_block(self, obj: UserInfo) -> bool:
        """判断用户是否被登录封锁。

        Args:
            obj: UserInfo 模型实例。

        Returns:
            用户是否被封锁。
        """
        return LoginBlockUtil.is_user_block(obj.username)

    @extend_schema_field(serializers.IntegerField)
    def get_online_count(self, obj: UserInfo) -> int:
        """获取用户在线连接数。

        Args:
            obj: UserInfo 模型实例。

        Returns:
            用户在线连接数。
        """
        return len(get_online_user_layers(obj.pk))

    def validate(self, attrs: dict) -> dict:
        """验证用户数据，处理密码加密。

        Args:
            attrs: 待验证的属性字典。

        Returns:
            验证后的属性字典。
        """
        password = attrs.get('password')
        if password:
            if self.request.method == 'POST':
                try:
                    attrs['password'] = make_password(AESCipherV2(attrs.get('username')).decrypt(password))
                except Exception as e:
                    attrs['password'] = make_password(attrs.get('password'))
                    logger.warning(f'create user and set password failed:{e}. so set default password')
                if not check_password_rules(password):
                    raise ValidationError(_('Password does not match security rules'))
            else:
                raise ValidationError(_('Abnormal password field'))
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """重置密码序列化器。"""

    password = serializers.CharField(
        min_length=5, max_length=128, required=True, write_only=True, label=_('Password'),
        help_text=_('New password, encrypted with AES before transmission')
    )

    def update(self, instance: UserInfo, validated_data: dict) -> UserInfo:
        """更新用户密码。

        Args:
            instance: 待更新的 UserInfo 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 UserInfo 实例。
        """
        password = AESCipherV2(instance.username).decrypt(validated_data.get('password'))
        if not check_password_rules(password, instance.is_superuser):
            raise serializers.ValidationError(_('Password does not match security rules'))

        instance.set_password(password)
        instance.modifier = self.context.get('request').user
        instance.save(update_fields=['password', 'modifier'])
        return instance
