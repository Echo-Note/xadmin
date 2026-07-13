"""用户配置视图。"""

from drf_spectacular.plumbing import build_basic_type, build_object_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiRequest
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.common.core.auth import auth_required
from apps.common.core.config import UserConfig, SysConfig
from apps.common.core.filter import OwnerUserFilter
from apps.common.core.response import ApiResponse
from apps.common.swagger.utils import get_default_response_schema
from apps.system.models import UserPersonalConfig
from apps.system.serializers.config import UserPersonalConfigSerializer


def config_response_schema() -> dict:
    """返回配置接口的响应 schema。

    Returns:
        配置响应 schema 字典。
    """
    return get_default_response_schema({'config': build_object_type(), 'auth': build_basic_type(OpenApiTypes.STR)})


class ConfigsViewSet(GenericViewSet):
    """配置信息视图集。"""

    queryset = UserPersonalConfig.objects.none()
    serializer_class = UserPersonalConfigSerializer
    ordering_fields = ['created_time']
    lookup_field = 'key'
    permission_classes = []
    filter_backends = [OwnerUserFilter]

    @extend_schema(responses=config_response_schema())
    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """获取指定 key 的配置值。"""
        value_key = self.kwargs[self.lookup_field]
        if value_key:
            if request.user and request.user.is_authenticated:
                config = UserConfig(request.user).get_value(value_key, ignore_access=False)
            else:
                config = SysConfig.get_value(value_key, ignore_access=False)
            if config is not None:
                if not isinstance(config, dict):
                    config = {'value': config, 'key': self.kwargs[self.lookup_field]}
                return ApiResponse(config=config, auth=f"{request.user}")
        return ApiResponse(config={}, auth=f"{request.user}")

    @extend_schema(responses=config_response_schema(), request=OpenApiRequest(build_object_type()))
    @auth_required
    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        """更新指定 key 的配置值。"""
        value_key = self.kwargs[self.lookup_field]
        if value_key:
            config = UserConfig(request.user).get_value(value_key, ignore_access=False)
            if config is not None:
                if isinstance(config, dict):
                    config.update({key: request.data.get(key, value) for key, value in config.items()})
                else:
                    config = request.data
                UserConfig(request.user).set_value(value_key, config, is_active=True, access=True)
        return self.retrieve(request, *args, **kwargs)

    @extend_schema(responses=config_response_schema())
    @auth_required
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """删除指定 key 的配置值。"""
        value_key = self.kwargs[self.lookup_field]
        if value_key:
            UserConfig(request.user).del_value(value_key)
        return self.retrieve(request, *args, **kwargs)
