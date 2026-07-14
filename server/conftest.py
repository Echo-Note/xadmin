"""pytest 全局 fixtures。"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.common.local import thread_local

User = get_user_model()


@pytest.fixture(autouse=True)
def _cleanup_request_context() -> None:
    """清理线程局部请求上下文，防止测试间 request user 泄漏。

    RequestMiddleware 在请求处理时将 request 写入 thread_local.current_request，
    但请求结束后不清除。这会导致后续测试中 pre_save 信号通过 _get_request_user()
    拿到上一个测试的已失效用户对象，触发 FK 约束违反。
    """
    # 测试前清除上一个测试残留的请求上下文
    if hasattr(thread_local, 'current_request'):
        delattr(thread_local, 'current_request')
    yield
    # 测试后清除本测试残留的请求上下文
    if hasattr(thread_local, 'current_request'):
        delattr(thread_local, 'current_request')


@pytest.fixture
def admin_user(db) -> User:
    """管理员用户——用 ORM 创建，密码自动哈希。"""
    user = User.objects.filter(username='admin').first()
    if not user:
        user = User.objects.create_superuser(
            username='admin', password='admin123', email='admin@test.com'
        )
        # 设置 self-FK 指向自己
        User.objects.filter(pk=user.pk).update(creator=user, modifier=user)
    return user


@pytest.fixture
def api_client() -> APIClient:
    """未认证的 API 客户端。"""
    return APIClient(HTTP_USER_AGENT='Mozilla/5.0 TestClient')


@pytest.fixture
def auth_client(db, admin_user: User) -> APIClient:
    """已认证的管理员 API 客户端。"""
    client = APIClient(HTTP_USER_AGENT='Mozilla/5.0 TestClient')
    client.force_authenticate(user=admin_user)
    return client
