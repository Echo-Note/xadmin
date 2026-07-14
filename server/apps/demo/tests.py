"""演示应用的测试用例——FileUploadMixin 文件上传功能。"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.common.core.modelset import BaseModelSet, ImportExportDataAction, FileUploadMixin
from apps.demo.models import Book
from apps.demo.serializers.book import BookSerializer


class _TestBaseViewSet(BaseModelSet, ImportExportDataAction):
    """测试基类，避免依赖 views.py 中错误的相对导入。"""

    queryset = Book.objects.all()
    serializer_class = BookSerializer
    ordering_fields = ['created_time']
    pagination_class = None


class BookUploadViewSet(FileUploadMixin, _TestBaseViewSet):
    """混入 FileUploadMixin 的测试视图集。"""

    FILE_UPLOAD_FIELDS = ['cover', 'book_file']
    FILE_UPLOAD_TYPE = ['png', 'jpg', 'jpeg', 'pdf', 'txt']


# ---------- 模块级 fixtures ----------

@pytest.fixture
def factory():
    """APIRequestFactory 实例。"""
    return APIRequestFactory()


# ---------- 辅助函数 ----------

def _make_file(name: str, content: bytes = b'test content') -> SimpleUploadedFile:
    """创建测试用上传文件。"""
    return SimpleUploadedFile(name, content, content_type='application/octet-stream')


def _upload(factory, admin_user, viewset_cls, action: str, field: str,
            file_name: str, content: bytes = b'test content', code: int = 1000):
    """执行一次上传请求并返回 response 的 data。

    Args:
        factory: APIRequestFactory 实例。
        admin_user: 认证用户。
        viewset_cls: 视图集类。
        action: action 方法名（如 'cover_upload'）。
        field: 表单字段名（如 'cover'）。
        file_name: 文件名。
        content: 文件内容。
        code: 期望的响应码，默认 1000。

    Returns:
        response.data 字典。
    """
    f = _make_file(file_name, content)
    req = factory.post('/', {field: f}, format='multipart')
    force_authenticate(req, user=admin_user)
    view = viewset_cls.as_view({'post': action})
    resp = view(req)
    assert resp.data['code'] == code, f"期望 code={code}, 实际 {resp.data}"
    return resp.data


class TestFileUploadMixin:

    # ---------- 接口生成 ----------

    def test_upload_actions_exist(self):
        assert hasattr(BookUploadViewSet, 'cover_upload')
        assert hasattr(BookUploadViewSet, 'book_file_upload')

    def test_fields_not_in_list_not_generated(self):
        assert not hasattr(BookUploadViewSet, 'avatar_upload')

    def test_action_url_path(self):
        """DRF @action 将 url_path 直接设置为函数属性，不在 kwargs 中。"""
        assert BookUploadViewSet.cover_upload.url_path == 'cover-upload'
        assert BookUploadViewSet.book_file_upload.url_path == 'book_file-upload'

    # ---------- 正常上传 ----------

    def test_upload_cover_success(self, factory, admin_user):
        data = _upload(factory, admin_user, BookUploadViewSet, 'cover_upload', 'cover', 'cover.png', b'hello world')
        assert data['data']['field'] == 'cover'
        assert data['data']['file_name'] == 'cover.png'
        assert data['data']['file_size'] == 11
        assert 'hash' in data['data']
        assert 'path' in data['data']
        assert data['data']['success'] is True

    def test_upload_book_file_success(self, factory, admin_user):
        data = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'doc.pdf', b'pdf')
        assert data['data']['field'] == 'book_file'
        assert data['data']['success'] is True

    # ---------- 幂等性（去重） ----------

    def test_same_content_same_hash_and_path(self, factory, admin_user):
        content = b'idempotent test content'
        d1 = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'same.txt', content)['data']
        d2 = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'renamed.txt', content)['data']
        assert d1['hash'] == d2['hash'], "相同内容 → 相同 hash"
        assert d1['path'] == d2['path'], "相同内容 → 相同路径"

    def test_different_content_different_hash(self, factory, admin_user):
        d1 = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'a.txt', b'content A')['data']
        d2 = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'b.txt', b'different B')['data']
        assert d1['hash'] != d2['hash']
        assert d1['path'] != d2['path']

    # ---------- 文件类型校验 ----------

    def test_unsupported_file_type_rejected(self, factory, admin_user):
        # 当前实现中校验失败返回 code=1001+错误详情
        data = _upload(factory, admin_user, BookUploadViewSet, 'cover_upload', 'cover', 'video.mp4', code=1001)
        assert '不支持' in data['detail']

    def test_allowed_type_accepted(self, factory, admin_user):
        _upload(factory, admin_user, BookUploadViewSet, 'cover_upload', 'cover', 'photo.png', b'img', code=1000)

    # ---------- 文件大小校验 ----------

    def test_file_size_limit_respected(self, factory, admin_user):
        """设置 FILE_UPLOAD_MAX_SIZE 后超限文件应被拒绝。"""
        class LimitedViewSet(FileUploadMixin, _TestBaseViewSet):
            FILE_UPLOAD_FIELDS = ['book_file']
            FILE_UPLOAD_TYPE = None
            FILE_UPLOAD_MAX_SIZE = 10  # 10 字节限制

        data = _upload(factory, admin_user, LimitedViewSet, 'book_file_upload', 'book_file',
                       'big.txt', b'x' * 100, code=1001)
        assert '大小' in data['detail'] or '不能超过' in data['detail']

    # ---------- 错误处理 ----------

    def test_no_file_error(self, factory, admin_user):
        req = factory.post('/', {}, format='multipart')
        force_authenticate(req, user=admin_user)
        resp = BookUploadViewSet.as_view({'post': 'cover_upload'})(req)
        assert resp.data['code'] == 1001

    def test_non_file_field_error(self, admin_user):
        class BadViewSet(FileUploadMixin, _TestBaseViewSet):
            FILE_UPLOAD_FIELDS = ['name']
            FILE_UPLOAD_TYPE = None

        view = BadViewSet()
        view.get_queryset = lambda: Book.objects.all()
        req = APIRequestFactory().post('/')
        force_authenticate(req, user=admin_user)
        view.request = req

        error = view._resolve_field('name')
        assert error is not None and error.data['code'] == 1001
        assert '不是文件类型' in error.data['detail']

    def test_field_not_exist_error(self, admin_user):
        view = BookUploadViewSet()
        view.get_queryset = lambda: Book.objects.all()
        req = APIRequestFactory().post('/')
        force_authenticate(req, user=admin_user)
        view.request = req

        error = view._resolve_field('unknown_field')
        assert error is not None and error.data['code'] == 1001
        assert '不存在' in error.data['detail']

    # ---------- 未认证 ----------

    def test_unauthenticated_rejected(self, factory):
        req = factory.post('/', {'cover': _make_file('test.png')}, format='multipart')
        resp = BookUploadViewSet.as_view({'post': 'cover_upload'})(req)
        assert resp.status_code in (401, 403)

    # ---------- 响应格式 ----------

    def test_success_response_fields(self, factory, admin_user):
        data = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'data.txt', b'resp fields')
        for key in ('field', 'file_name', 'file_size', 'hash', 'path', 'success'):
            assert key in data['data'], f"应包含 {key}"

    # ---------- MD5 哈希正确性 ----------

    def test_hash_matches_expected_md5(self, factory, admin_user):
        content = b'Hello, this is a test file for MD5 verification!'
        expected = '90247da7d7abe902d97f2c1377d9b8e5'
        data = _upload(factory, admin_user, BookUploadViewSet, 'book_file_upload', 'book_file', 'md5.txt', content)
        assert data['data']['hash'] == expected

    # ---------- 多文件上传 ----------

    def test_single_file_default(self, factory, admin_user):
        _upload(factory, admin_user, BookUploadViewSet, 'cover_upload', 'cover', 'test.png')

    def test_multiple_files_configured(self, factory, admin_user):
        class MultiViewSet(FileUploadMixin, _TestBaseViewSet):
            FILE_UPLOAD_FIELDS = ['book_file']
            FILE_UPLOAD_ALLOW_MULTIPLE = True
            FILE_UPLOAD_TYPE = None

        data = _upload(factory, admin_user, MultiViewSet, 'book_file_upload', 'book_file', 'a.txt', b'content1')
        assert data['data']['success'] is True
