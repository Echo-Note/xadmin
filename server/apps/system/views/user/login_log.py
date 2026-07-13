"""用户登录日志视图。"""

from django.db.models import QuerySet
from rest_framework.mixins import ListModelMixin
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.common.core.modelset import SearchColumnsAction
from apps.common.core.response import ApiResponse
from apps.system.models import UserLoginLog
from apps.system.serializers.log import UserLoginLogSerializer


class UserLoginLogViewSet(ListModelMixin, SearchColumnsAction, GenericViewSet):
    """用户登录日志视图集。"""

    queryset = UserLoginLog.objects.all()
    serializer_class = UserLoginLogSerializer

    ordering_fields = ['created_time']

    def get_queryset(self) -> QuerySet:
        """返回当前用户的登录日志查询集。"""
        return self.queryset.filter(creator=self.request.user)

    def list(self, request: Request, *args, **kwargs) -> Response:
        """获取当前用户的登录日志列表。"""
        data = super().list(request, *args, **kwargs).data
        return ApiResponse(data=data)
