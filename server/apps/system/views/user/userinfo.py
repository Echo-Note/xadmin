"""用户个人信息视图。"""

from django.conf import settings
from django.db.models import QuerySet
from drf_spectacular.plumbing import build_object_type, build_basic_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiRequest
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.core.modelset import DetailUpdateModelSet, UploadFileAction, ChoicesAction
from apps.common.core.response import ApiResponse
from apps.common.swagger.utils import get_default_response_schema
from apps.common.utils import get_logger
from apps.common.utils.verify_code import TokenTempCache
from apps.settings.utils.security import ResetBlockUtil
from apps.system.models import UserInfo
from apps.system.notifications import ResetPasswordSuccessMsg
from apps.system.serializers.userinfo import UserInfoSerializer, ChangePasswordSerializer
from apps.system.utils.auth import verify_sms_email_code

logger = get_logger(__name__)


class UserInfoViewSet(DetailUpdateModelSet, ChoicesAction, UploadFileAction):
    """用户个人信息视图集。"""

    serializer_class = UserInfoSerializer
    FILE_UPLOAD_FIELD = 'avatar'
    choices_models = [UserInfo]
    queryset = UserInfo.objects.none()

    def get_object(self) -> UserInfo:
        """返回当前登录用户。"""
        return self.request.user

    def get_queryset(self) -> QuerySet:
        """返回当前用户的查询集。"""
        return UserInfo.objects.filter(pk=self.request.user.pk)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """获取当前用户信息。"""
        data = super().retrieve(request, *args, **kwargs).data
        return ApiResponse(**data, config={
            'FRONT_END_WEB_WATERMARK_ENABLED': settings.FRONT_END_WEB_WATERMARK_ENABLED
        })

    @extend_schema(responses=get_default_response_schema())
    @action(methods=['post'], detail=False, url_path='reset-password', serializer_class=ChangePasswordSerializer)
    def reset_password(self, request: Request, *args, **kwargs) -> Response:
        """修改当前用户密码。"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        ResetPasswordSuccessMsg(instance, request).publish_async()
        return ApiResponse()

    @extend_schema(
        request=OpenApiRequest(
            build_object_type(properties={'file': build_basic_type(OpenApiTypes.BINARY)})
        ),
        responses=get_default_response_schema()
    )
    @action(methods=['post'], detail=False, parser_classes=(MultiPartParser,))
    def upload(self, request: Request, *args, **kwargs) -> Response:
        """上传当前用户头像。"""
        return super().upload(request, *args, **kwargs)

    @extend_schema(
        request=OpenApiRequest(
            build_object_type(
                properties={
                    'verify_token': build_basic_type(OpenApiTypes.STR),
                    'verify_code': build_basic_type(OpenApiTypes.STR),
                },
                required=['verify_token', 'verify_code'],
            )
        ),
        responses=get_default_response_schema()
    )
    @action(methods=['post'], detail=False, url_path='bind')
    def bind(self, request: Request, *args, **kwargs) -> Response:
        """绑定当前用户邮箱或手机。"""
        query_key, target, verify_token = verify_sms_email_code(request, ResetBlockUtil)
        instance = UserInfo.objects.filter(**{query_key: target}).first()
        if instance:
            setattr(instance, query_key, '')
            instance.save(update_fields=(query_key,))
        setattr(request.user, query_key, target)
        request.user.save(update_fields=(query_key,))
        TokenTempCache.expired_cache_token(verify_token)
        return ApiResponse()
