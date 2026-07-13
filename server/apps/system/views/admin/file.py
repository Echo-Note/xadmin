"""文件上传管理视图。"""

from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from drf_spectacular.plumbing import build_object_type, build_basic_type, build_array_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiRequest, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.core.config import SysConfig, UserConfig
from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet
from apps.common.core.response import ApiResponse
from apps.common.core.throttle import UploadThrottle
from apps.common.swagger.utils import get_default_response_schema
from apps.common.utils import get_logger
from apps.system.models import UploadFile, UserInfo
from apps.system.serializers.upload import UploadFileSerializer

logger = get_logger(__name__)


def get_upload_max_size(user_obj: UserInfo) -> int:
    """获取用户允许上传的最大文件大小。

    Args:
        user_obj: 用户对象。

    Returns:
        系统配置和用户配置中的较小值。
    """
    return min(SysConfig.FILE_UPLOAD_SIZE, UserConfig(user_obj).FILE_UPLOAD_SIZE)


class UploadFileFilter(BaseFilterSet):
    """上传文件过滤器。"""

    filename = filters.CharFilter(field_name='filename', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = UploadFile
        fields = ['filename', 'mime_type', 'md5sum', 'description', 'is_upload', 'is_tmp']


class UploadFileViewSet(BaseModelSet):
    """上传文件视图集。"""

    queryset = UploadFile.objects.all()
    serializer_class = UploadFileSerializer
    ordering_fields = ['created_time', 'filesize']
    filterset_class = UploadFileFilter

    @extend_schema(
        responses=get_default_response_schema({
            'data': build_object_type(
                properties={
                    'file_upload_size': build_basic_type(OpenApiTypes.NUMBER),
                }
            )
        })
    )
    @action(methods=['get'], detail=False)
    def config(self, request: Request, *args, **kwargs) -> Response:
        """获取上传文件大小限制配置。"""
        return ApiResponse(data={'file_upload_size': get_upload_max_size(request.user)})

    @extend_schema(
        description="文件上传",
        request=OpenApiRequest(
            build_object_type(properties={'file': build_array_type(build_basic_type(OpenApiTypes.BINARY))})
        ),
        responses={
            200: inline_serializer(name='result', fields={
                'code': serializers.IntegerField(),
                'detail': serializers.CharField(),
                'data': UploadFileSerializer(many=True)
            })
        }
    )
    @action(methods=['post'], detail=False, throttle_classes=[UploadThrottle, ], parser_classes=(MultiPartParser,))
    def upload(self, request: Request, *args, **kwargs) -> Response:
        """上传文件，校验文件大小和类型。"""

        files = request.FILES.getlist('file', [])
        result = []
        file_upload_max_size = get_upload_max_size(request.user)
        for file_obj in files:
            try:
                if file_obj.size > file_upload_max_size:
                    return ApiResponse(code=1003,
                                       detail=_("upload file size cannot exceed {}").format(file_upload_max_size))
            except Exception as e:
                logger.error(f"user:{request.user} upload file type error Exception:{e}")
                return ApiResponse(code=1002, detail=_("Wrong upload file type"))
            obj = UploadFile.objects.create(creator=request.user, filename=file_obj.name, is_upload=True, is_tmp=True,
                                            filepath=file_obj, mime_type=file_obj.content_type, filesize=file_obj.size)
            result.append(obj)
        return ApiResponse(data=self.get_serializer(result, many=True).data)
