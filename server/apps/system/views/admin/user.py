"""用户管理视图。"""

from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from drf_spectacular.plumbing import build_object_type, build_array_type, build_basic_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiRequest
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet, UploadFileAction, ImportExportDataAction
from apps.common.core.response import ApiResponse
from apps.common.swagger.utils import get_default_response_schema
from apps.common.utils import get_logger
from apps.message.utils import send_logout_msg
from apps.notifications.message import SiteMessageUtil
from apps.settings.utils.security import LoginBlockUtil
from apps.system.models import UserInfo
from apps.system.serializers.user import UserSerializer, ResetPasswordSerializer
from apps.system.utils.modelset import ChangeRolePermissionAction

logger = get_logger(__name__)


class UserFilter(BaseFilterSet):
    """用户过滤器。"""

    username = filters.CharFilter(field_name='username', lookup_expr='icontains')
    nickname = filters.CharFilter(field_name='nickname', lookup_expr='icontains')
    phone = filters.CharFilter(field_name='phone', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = UserInfo
        fields = ['username', 'nickname', 'phone', 'email', 'is_active', 'gender', 'pk', 'mode_type', 'dept']


class UserViewSet(BaseModelSet, UploadFileAction, ChangeRolePermissionAction, ImportExportDataAction):
    """用户视图集。"""

    FILE_UPLOAD_FIELD = 'avatar'
    queryset = UserInfo.objects.all()
    serializer_class = UserSerializer

    ordering_fields = ['date_joined', 'last_login', 'created_time']
    filterset_class = UserFilter

    # export_as_zip = True  导出zip压缩包，密码是用户名

    def perform_destroy(self, instance: UserInfo) -> tuple[int, dict]:
        """删除用户，禁止删除超级管理员。

        Args:
            instance: UserInfo 模型实例。

        Returns:
            删除的数量和各模型删除数量的字典。
        """
        if instance.is_superuser:
            raise Exception(_('The super administrator disallows deletion'))
        return instance.delete()

    @extend_schema(
        request=OpenApiRequest(
            build_object_type(
                properties={'pks': build_array_type(build_basic_type(OpenApiTypes.STR))},
                required=['pks'],
                description="主键列表"
            )
        ),
        responses=get_default_response_schema()
    )
    @action(methods=['post'], detail=False, url_path='batch-destroy')
    def batch_destroy(self, request: Request, *args, **kwargs) -> Response:
        """批量删除用户，排除超级管理员。"""
        self.queryset = self.queryset.filter(is_superuser=False)
        return super().batch_destroy(request, *args, **kwargs)

    @extend_schema(responses=get_default_response_schema())
    @action(methods=['post'], detail=True, url_path='reset-password', serializer_class=ResetPasswordSerializer)
    def reset_password(self, request: Request, *args, **kwargs) -> Response:
        """管理员重置用户密码。"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        SiteMessageUtil.notify_error(users=instance, title="密码重置成功", message="密码被管理员重置成功")
        return ApiResponse()

    @extend_schema(responses=get_default_response_schema(), request=None)
    @action(methods=['post'], detail=True)
    def unblock(self, request: Request, *args, **kwargs) -> Response:
        """解除用户登录封锁。"""
        instance = self.get_object()
        LoginBlockUtil.unblock_user(instance.username)
        return ApiResponse()

    @extend_schema(
        request=OpenApiRequest(
            build_object_type(
                properties={'channel_names': build_array_type(build_basic_type(OpenApiTypes.STR))},
                required=['channel_names'],
                description="列表"
            )
        ),
        responses=get_default_response_schema()
    )
    @action(methods=['post'], detail=True)
    def logout(self, request: Request, *args, **kwargs) -> Response:
        """强制下线指定用户的 WebSocket 连接。"""
        instance = self.get_object()
        channel_names = request.data.get('channel_names', [])
        send_logout_msg(instance.pk, channel_names)
        return ApiResponse()
