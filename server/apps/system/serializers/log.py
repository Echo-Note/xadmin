"""日志序列化器。"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.message.utils import get_online_user_layers
from apps.system.models import UserLoginLog, OperationLog

logger = get_logger(__name__)


class OperationLogSerializer(BaseModelSerializer):
    """操作日志序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = OperationLog
        fields = [
            'pk', 'module', 'creator', 'ipaddress', 'path', 'method', 'browser', 'system', 'request_uuid', 'exec_time',
            'response_code', 'status_code', 'body', 'response_result', 'created_time'
        ]

        table_fields = [
            'pk', 'module', 'creator', 'ipaddress', 'path', 'method', 'browser', 'system', 'exec_time', 'status_code',
            'created_time'
        ]
        read_only_fields = ['pk'] + list(set([x.name for x in OperationLog._meta.fields]))
        extra_kwargs = {'creator': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}'}}

    response_result = serializers.JSONField()
    body = serializers.JSONField()


class LoginLogSerializer(BaseModelSerializer):
    """登录日志序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserLoginLog
        fields = [
            'pk', 'creator', 'ipaddress', 'city', 'online', 'channel_name', 'login_type', 'browser', 'system', 'agent',
            'status', 'created_time'
        ]
        table_fields = [
            'pk', 'creator', 'ipaddress', 'city', 'online', 'channel_name', 'login_type', 'browser', 'system', 'status',
            'created_time'
        ]
        read_only_fields = ['pk', 'creator']
        extra_kwargs = {'creator': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}'}}

    online = serializers.SerializerMethodField(read_only=True, label=_('Online'))

    @extend_schema_field(serializers.IntegerField)
    def get_online(self, obj: UserLoginLog) -> int:
        """判断用户是否在线。

        Args:
            obj: UserLoginLog 模型实例。

        Returns:
            1 表示在线，0 表示离线，-1 表示非 WebSocket 登录方式。
        """
        if UserLoginLog.LoginTypeChoices.WEBSOCKET == obj.login_type:
            return obj.channel_name in get_online_user_layers(obj.creator.pk)
        return -1


class UserLoginLogSerializer(LoginLogSerializer):
    """用户登录日志序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserLoginLog
        fields = ['created_time', 'status', 'agent', 'city', 'login_type', 'system', 'browser', 'ipaddress']
        read_only_fields = [x.name for x in UserLoginLog._meta.fields]


class UserOnlineSerializer(LoginLogSerializer):
    """用户在线状态序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserLoginLog
        fields = ['pk', 'creator', 'channel_name', 'agent', 'city', 'system', 'browser', 'ipaddress', 'created_time']
        read_only_fields = [x.name for x in UserLoginLog._meta.fields]
        extra_kwargs = {'creator': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}'}}
