"""登录日志管理视图。"""


from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.core.filter import BaseFilterSet, PkMultipleFilter
from apps.common.core.modelset import ListDeleteModelSet, OnlyExportDataAction
from apps.common.core.response import ApiResponse
from apps.common.swagger.utils import get_default_response_schema
from apps.message.utils import send_logout_msg
from apps.system.models import UserLoginLog
from apps.system.serializers.log import LoginLogSerializer


class LoginLogFilter(BaseFilterSet):
    """登录日志过滤器。"""

    ipaddress = filters.CharFilter(field_name='ipaddress', lookup_expr='icontains')
    city = filters.CharFilter(field_name='city', lookup_expr='icontains')
    system = filters.CharFilter(field_name='system', lookup_expr='icontains')
    agent = filters.CharFilter(field_name='agent', lookup_expr='icontains')
    creator_id = PkMultipleFilter(input_type='api-search-user')

    class Meta:
        """过滤器元数据。"""

        model = UserLoginLog
        fields = ['login_type', 'ipaddress', 'city', 'system', 'creator_id', 'status', 'agent', 'created_time']


class LoginLogViewSet(ListDeleteModelSet, OnlyExportDataAction):
    """登录日志视图集。"""

    queryset = UserLoginLog.objects.all()
    serializer_class = LoginLogSerializer

    ordering_fields = ['created_time']
    filterset_class = LoginLogFilter

    @extend_schema(responses=get_default_response_schema(), request=None)
    @action(methods=['post'], detail=True)
    def logout(self, request: Request, *args, **kwargs) -> Response:
        """强制下线指定用户。"""
        instance = self.get_object()
        send_logout_msg(instance.creator.pk, [instance.channel_name])
        return ApiResponse()
