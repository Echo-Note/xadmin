"""令牌视图。"""

from drf_spectacular.plumbing import build_basic_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView

from apps.captcha.utils import CaptchaAuth
from apps.common.core.response import ApiResponse
from apps.common.swagger.utils import get_default_response_schema
from apps.common.utils.request import get_request_ident
from apps.common.utils.token import make_token_cache
from apps.system.utils.auth import get_token_lifetime


class TempTokenAPIView(GenericAPIView):
    """临时令牌视图。"""

    permission_classes = []
    authentication_classes = []

    @extend_schema(responses=get_default_response_schema({'token': build_basic_type(OpenApiTypes.STR)}))
    def get(self, request: Request) -> Response:
        """获取临时令牌，用于后续请求验证。"""
        token = make_token_cache(get_request_ident(request), time_limit=600, force_new=True).encode('utf-8')
        return ApiResponse(token=token)


class CaptchaAPIView(GenericAPIView):
    """图片验证码视图。"""

    permission_classes = []
    authentication_classes = []

    @extend_schema(
        responses=get_default_response_schema(
            {
                'captcha_image': build_basic_type(OpenApiTypes.STR),
                'captcha_key': build_basic_type(OpenApiTypes.STR),
                'length': build_basic_type(OpenApiTypes.NUMBER)
            }
        )
    )
    def get(self, request: Request) -> Response:
        """生成图片验证码。"""
        return ApiResponse(**CaptchaAuth(request=request).generate())


class RefreshTokenAPIView(TokenRefreshView):
    """刷新令牌视图。"""

    def post(self, request: Request, *args, **kwargs) -> Response:
        """刷新 JWT 令牌并返回令牌有效期。"""
        data = super().post(request, *args, **kwargs).data
        data.update(get_token_lifetime(request.user))
        return ApiResponse(data=data)
