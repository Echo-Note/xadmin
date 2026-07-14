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
        extra_kwargs = {
            'creator': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}',
                        'label': _('Creator'), 'help_text': _('User who triggered this operation')},
            'module': {'label': _('Module'), 'help_text': _('Module name of the operation')},
            'ipaddress': {'label': _('IpAddress'), 'help_text': _('Client IP address of the request')},
            'path': {'label': _('URL path'), 'help_text': _('Request URL path')},
            'method': {'label': _('Request method'), 'help_text': _('HTTP request method')},
            'browser': {'label': _('Browser'), 'help_text': _('Client browser information')},
            'system': {'label': _('System'), 'help_text': _('Client operating system information')},
            'request_uuid': {'label': _('Request ID'), 'help_text': _('Unique identifier of the request')},
            'exec_time': {'label': _('Execution time'), 'help_text': _('Request execution time in seconds')},
            'response_code': {'label': _('Response code'),
                              'help_text': _('Business response code returned to the client')},
            'status_code': {'label': _('Status code'), 'help_text': _('HTTP status code of the response')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
        }

    response_result = serializers.JSONField(label=_('Response result'),
                                            help_text=_('Response result body of the request'))
    body = serializers.JSONField(label=_('Request body'), help_text=_('Request body content of the operation'))


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
        extra_kwargs = {
            'creator': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}',
                        'label': _('Creator'), 'help_text': _('User who triggered this login')},
            'ipaddress': {'label': _('IpAddress'), 'help_text': _('Client IP address of the login')},
            'city': {'label': _('Login city'), 'help_text': _('City inferred from the login IP address')},
            'channel_name': {'label': _('Channel name'), 'help_text': _('WebSocket channel name of the login session')},
            'login_type': {'label': _('Login type'), 'help_text': _('Method used for this login')},
            'browser': {'label': _('Browser'), 'help_text': _('Client browser information')},
            'system': {'label': _('System'), 'help_text': _('Client operating system information')},
            'agent': {'label': _('Agent'), 'help_text': _('Client user agent string')},
            'status': {'label': _('Login status'), 'help_text': _('Whether the login was successful')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
        }

    online = serializers.SerializerMethodField(read_only=True, label=_('Online'),
                                               help_text=_('Whether the user is currently online'))

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
        extra_kwargs = {
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
            'status': {'label': _('Login status'), 'help_text': _('Whether the login was successful')},
            'agent': {'label': _('Agent'), 'help_text': _('Client user agent string')},
            'city': {'label': _('Login city'), 'help_text': _('City inferred from the login IP address')},
            'login_type': {'label': _('Login type'), 'help_text': _('Method used for this login')},
            'system': {'label': _('System'), 'help_text': _('Client operating system information')},
            'browser': {'label': _('Browser'), 'help_text': _('Client browser information')},
            'ipaddress': {'label': _('IpAddress'), 'help_text': _('Client IP address of the login')},
        }


class UserOnlineSerializer(LoginLogSerializer):
    """用户在线状态序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserLoginLog
        fields = ['pk', 'creator', 'channel_name', 'agent', 'city', 'system', 'browser', 'ipaddress', 'created_time']
        read_only_fields = [x.name for x in UserLoginLog._meta.fields]
        extra_kwargs = {
            'creator': {'attrs': ['pk', 'username'], 'read_only': True, 'format': '{username}',
                        'label': _('Creator'), 'help_text': _('User who triggered this login')},
            'channel_name': {'label': _('Channel name'),
                             'help_text': _('WebSocket channel name of the login session')},
            'agent': {'label': _('Agent'), 'help_text': _('Client user agent string')},
            'city': {'label': _('Login city'), 'help_text': _('City inferred from the login IP address')},
            'system': {'label': _('System'), 'help_text': _('Client operating system information')},
            'browser': {'label': _('Browser'), 'help_text': _('Client browser information')},
            'ipaddress': {'label': _('IpAddress'), 'help_text': _('Client IP address of the login')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
        }
