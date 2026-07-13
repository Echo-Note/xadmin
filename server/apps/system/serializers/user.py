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
            'pk': {'read_only': True}, 'last_login': {'read_only': True}, 'date_joined': {'read_only': True},
            'avatar': {'read_only': True}, 'password': {'write_only': True},
            'roles': {'required': False, 'attrs': ['pk', 'name', 'code'], 'format': '{name}', 'many': True},
            'rules': {'required': False, 'attrs': ['pk', 'name', 'get_mode_type_display'], 'format': '{name}',
                      'many': True},
            'dept': {'required': False, 'attrs': ['pk', 'name', 'parent_id'], 'format': '{name}'},
            'email': {'validators': [UniqueValidator(queryset=UserInfo.objects.all())]},
            'phone': {'validators': [UniqueValidator(queryset=UserInfo.objects.all())]}
        }

    block = input_wrapper(serializers.SerializerMethodField)(read_only=True, input_type='boolean',
                                                             label=_('Login blocked'))
    online_count = input_wrapper(serializers.SerializerMethodField)(read_only=True, input_type='number',
                                                                    label=_('Online count'))

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
        min_length=5, max_length=128, required=True, write_only=True, label=_('Password')
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
