"""
ASGI config for server project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os
import uuid
from collections.abc import Callable
from typing import Any

from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.core.handlers.asgi import ASGIRequest
from django.utils.module_loading import import_string

from apps.common.utils import get_logger
from server.utils import set_current_request

logger = get_logger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
django_asgi_app = get_asgi_application()

# 写到上面会导致gunicorn启动失败
from apps.message.routing import urlpatterns as message_urlpatterns

urlpatterns = message_urlpatterns


@database_sync_to_async
def get_signature_user(scope: dict) -> object | None:
    """从 WebSocket 连接的 scope 中通过 DRF 认证后端解析用户。

    Args:
        scope: ASGI 连接 scope 字典。

    Returns:
        认证成功时返回用户对象，失败时返回 None。
    """
    if scope['type'] == 'websocket':
        scope['method'] = 'GET'

    request = ASGIRequest(scope, None)
    for backend_str in settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES'):
        try:
            backend = import_string(backend_str)
            user, auth = backend().authenticate(request)
            if user:
                user.auth = auth
                request.user = user
                request.request_uuid = uuid.uuid4()
                set_current_request(request)
                logger.info(f"web socket auth success")
                return user
        except Exception as e:
            logger.warning(f"web socket auth failed by {backend_str}. Exception: {e}")
    logger.error(f"web socket auth failed.")
    return None


class WsSignatureAuthMiddleware:
    """WebSocket 签名认证中间件，在连接建立时解析并注入用户信息。"""

    def __init__(self, app: Callable) -> None:
        """初始化中间件。

        Args:
            app: 下游 ASGI 应用可调用对象。
        """
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> Any:
        """处理 ASGI 连接，认证用户后注入 scope 并传递给下游应用。

        Args:
            scope: ASGI 连接 scope 字典。
            receive: 接收消息的可调用对象。
            send: 发送消息的可调用对象。

        Returns:
            下游 ASGI 应用的返回值。
        """
        user = await get_signature_user(scope)
        if user:
            scope['user'] = user
        return await self.app(scope, receive, send)


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            WsSignatureAuthMiddleware(
                AuthMiddlewareStack(URLRouter(urlpatterns))
            )
        ),
    }
)
