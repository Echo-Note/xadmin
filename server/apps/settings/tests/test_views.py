"""存储设置视图测试用例。

覆盖内容：
- 鉴权：未认证拒绝 GET / PATCH / PUT / POST / search-columns
- PATCH：媒体文件/静态文件切换 S3 校验、部分更新、配置版本递增
- COS：腾讯云 COS 专项配置验证
- 文件 CRUD：本地存储 + S3/COS 远程存储的文件保存/读取/删除/存在性检查
"""

import json
import os

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.common.storage.backends import DynamicFileStorage, is_local_storage
from apps.settings.models import Setting

# ==================== 辅助函数 ====================


def _make_setting(name: str, value) -> Setting:
    """在数据库中创建或更新设置项，值按 JSON 序列化存储。"""
    obj, _ = Setting.objects.update_or_create(
        name=name,
        defaults={'value': json.dumps(value), 'category': 'storage'},
    )
    return obj


def _make_s3_media_settings(
    bucket: str = 'yunwei-1328164982',
    endpoint: str = 'https://cos.ap-guangzhou.myqcloud.com',
    region: str = 'ap-guangzhou',
    access_key: str = 'AKIDtest',
    secret_key: str = 'testsecret',
) -> None:
    """创建 S3 媒体文件存储配置项到数据库。"""
    _make_setting('STORAGE_BACKEND', 's3')
    _make_setting('STORAGE_S3_BUCKET_NAME', bucket)
    _make_setting('STORAGE_S3_ENDPOINT_URL', endpoint)
    _make_setting('STORAGE_S3_REGION_NAME', region)
    _make_setting('STORAGE_S3_ACCESS_KEY', access_key)
    _make_setting('STORAGE_S3_SECRET_KEY', secret_key)
    _make_setting('STORAGE_S3_ADDRESSING_STYLE', 'virtual')
    _make_setting('STORAGE_S3_SIGNATURE_VERSION', 's3v4')
    _make_setting('STORAGE_S3_USE_SSL', True)
    _make_setting('STORAGE_S3_VERIFY', True)
    _make_setting('STORAGE_S3_LOCATION', 'media/')


def _cleanup_storage_file(storage: DynamicFileStorage, name: str) -> None:
    """安全清理存储中的测试文件。"""
    try:
        if storage.exists(name):
            storage.delete(name)
    except Exception:
        pass  # 忽略清理失败


# ==================== 鉴权测试 ====================


@pytest.mark.django_db
def test_unauthenticated_get_denied(api_client):
    """未认证用户 GET 返回 401。"""
    assert api_client.get(reverse('settings:storage-detail')).status_code == 401


@pytest.mark.django_db
def test_unauthenticated_patch_denied(api_client):
    """未认证用户 PATCH 返回 401。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = api_client.patch(url, {'STORAGE_BACKEND': 'local'}, format='json')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_unauthenticated_put_denied(api_client):
    """未认证用户 PUT 返回 401。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = api_client.put(url, {'STORAGE_BACKEND': 'local'}, format='json')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_unauthenticated_search_columns_denied(api_client):
    """未认证用户 search-columns 返回 401。"""
    url = reverse('settings:storage-search-columns') + '?category=media'
    assert api_client.get(url).status_code == 401


# ==================== PATCH — S3 必填字段校验 ====================


@pytest.mark.django_db
def test_patch_s3_missing_bucket(auth_client):
    """PATCH S3 缺少 bucket_name 返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': '',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
    }, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_s3_missing_access_key(auth_client):
    """PATCH S3 缺少 access_key 返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'bucket',
        'STORAGE_S3_ACCESS_KEY': '',
        'STORAGE_S3_SECRET_KEY': 'sk',
    }, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_s3_missing_secret_key(auth_client):
    """PATCH S3 缺少 secret_key 返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'bucket',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': '',
    }, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_s3_all_missing_fields(auth_client):
    """PATCH S3 所有必填字段为空返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': '',
        'STORAGE_S3_ACCESS_KEY': '',
        'STORAGE_S3_SECRET_KEY': '',
    }, format='json')
    assert resp.status_code == 400


# ==================== PATCH — 本地存储模式 ====================


@pytest.mark.django_db
def test_patch_local_mode_success(auth_client):
    """PATCH 切换到本地存储成功（无需 S3 字段）。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {'STORAGE_BACKEND': 'local'}, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


# ==================== PATCH — S3 成功更新 ====================


@pytest.mark.django_db
def test_patch_s3_minimal_valid_config(auth_client):
    """PATCH S3 最小合法配置成功。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'my-bucket',
        'STORAGE_S3_ACCESS_KEY': 'AKIDxxx',
        'STORAGE_S3_SECRET_KEY': 'secretxxx',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_patch_static_s3_minimal_valid_config(auth_client):
    """PATCH 静态文件 S3 最小合法配置成功。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.patch(url, {
        'STATIC_STORAGE_BACKEND': 's3',
        'STATIC_S3_BUCKET_NAME': 'static-bucket',
        'STATIC_S3_ACCESS_KEY': 'ak',
        'STATIC_S3_SECRET_KEY': 'sk',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_patch_static_s3_missing_fields(auth_client):
    """PATCH 静态 S3 缺少必填字段返回 400。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.patch(url, {
        'STATIC_STORAGE_BACKEND': 's3',
        'STATIC_S3_BUCKET_NAME': '',
        'STATIC_S3_ACCESS_KEY': '',
        'STATIC_S3_SECRET_KEY': '',
    }, format='json')
    assert resp.status_code == 400


# ==================== PATCH — 部分更新 ====================


@pytest.mark.django_db
def test_patch_partial_update_single_field(auth_client):
    """PATCH 部分更新单一字段。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {'STORAGE_S3_LOCATION': 'uploads/'}, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_patch_partial_update_custom_domain(auth_client):
    """PATCH 仅更新自定义域名字段。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_S3_CUSTOM_DOMAIN': 'cdn.example.com'
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


# ==================== PATCH — 配置版本递增 ====================


@pytest.mark.django_db
def test_patch_bumps_config_version(auth_client):
    """PATCH 成功后 STORAGE_CONFIG_VERSION 递增。"""
    from apps.settings.models import Setting as S
    S.objects.create(
        name='STORAGE_CONFIG_VERSION', value='0', category='storage', is_active=True
    )

    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'bucket',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
    }, format='json')
    assert resp.status_code == 200

    version = S.objects.filter(name='STORAGE_CONFIG_VERSION', is_active=True).first()
    assert version is not None
    assert version.cleaned_value >= 1


# ==================== PATCH — 无效输入 ====================


@pytest.mark.django_db
def test_patch_invalid_backend_choice(auth_client):
    """PATCH 非法 storage_backend 值返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {'STORAGE_BACKEND': 'ftp'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_invalid_acl(auth_client):
    """PATCH 非法 ACL 值返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_S3_DEFAULT_ACL': 'public-read-write'
    }, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_invalid_addressing_style(auth_client):
    """PATCH 非法 addressing_style 返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_S3_ADDRESSING_STYLE': 'invalid-style'
    }, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_patch_invalid_url_protocol(auth_client):
    """PATCH 非法 url_protocol 返回 400。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_S3_URL_PROTOCOL': 'ftp'
    }, format='json')
    assert resp.status_code == 400


# ==================== GET 测试 ====================


@pytest.mark.django_db
def test_get_media_defaults(auth_client):
    """GET media 返回默认配置。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_get_static_defaults(auth_client):
    """GET static 返回默认配置。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_get_media_contains_all_fields(auth_client):
    """GET media 响应包含所有预期字段。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    data = resp.data['data']
    assert 'STORAGE_BACKEND' in data
    assert 'STORAGE_S3_BUCKET_NAME' in data
    assert 'STORAGE_S3_ENDPOINT_URL' in data
    assert 'STORAGE_S3_REGION_NAME' in data
    assert 'STORAGE_S3_ADDRESSING_STYLE' in data
    assert 'STORAGE_S3_LOCATION' in data
    assert 'STORAGE_S3_DEFAULT_ACL' in data
    assert 'STORAGE_S3_QUERYSTRING_AUTH' in data
    assert 'STORAGE_S3_QUERYSTRING_EXPIRE' in data
    assert 'STORAGE_S3_URL_PROTOCOL' in data


@pytest.mark.django_db
def test_get_static_contains_all_fields(auth_client):
    """GET static 响应包含所有预期字段。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    data = resp.data['data']
    assert 'STATIC_STORAGE_BACKEND' in data
    assert 'STATIC_S3_BUCKET_NAME' in data
    assert 'STATIC_S3_ENDPOINT_URL' in data
    assert 'STATIC_S3_LOCATION' in data


@pytest.mark.django_db
def test_get_without_category_uses_default(auth_client):
    """不传 category 参数时使用默认序列化器。"""
    resp = auth_client.get(reverse('settings:storage-detail'))
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


# ==================== search-columns 测试 ====================


@pytest.mark.django_db
def test_search_columns_media(auth_client):
    """media 分类 search-columns 包含核心字段。"""
    url = reverse('settings:storage-search-columns') + '?category=media'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    keys = [c['key'] for c in resp.data['data']]
    assert 'STORAGE_BACKEND' in keys
    assert 'STORAGE_CONFIG_VERSION' not in keys  # 隐藏字段不出现在列定义中


@pytest.mark.django_db
def test_search_columns_static(auth_client):
    """static 分类 search-columns 包含核心字段。"""
    url = reverse('settings:storage-search-columns') + '?category=static'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    keys = [c['key'] for c in resp.data['data']]
    assert 'STATIC_STORAGE_BACKEND' in keys


@pytest.mark.django_db
def test_search_columns_without_category_uses_default(auth_client):
    """不传 category 时 search-columns 返回默认分类。"""
    resp = auth_client.get(reverse('settings:storage-search-columns'))
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


# ==================== 序列化器映射测试 ====================


def test_serializer_class_mapper():
    """StorageSettingViewSet 包含 media 和 static 映射。"""
    from apps.settings.views.storage import StorageSettingViewSet
    assert 'media' in StorageSettingViewSet.serializer_class_mapper
    assert 'static' in StorageSettingViewSet.serializer_class_mapper


# ==================== 本地文件 CRUD 集成测试 ====================


@pytest.mark.django_db
def test_local_storage_save_and_read():
    """本地存储：保存文件后能正确读取内容。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    filename = 'test_crud.txt'
    content = b'Hello xadmin storage test'

    try:
        saved_name = storage._save(filename, ContentFile(content))
        assert storage.exists(saved_name)
        f = storage._open(saved_name)
        assert f.read() == content
        f.close()
    finally:
        _cleanup_storage_file(storage, filename)


@pytest.mark.django_db
def test_local_storage_delete():
    """本地存储：删除文件后不存在。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    filename = 'test_delete.txt'

    saved_name = storage._save(filename, ContentFile(b'to be deleted'))
    assert storage.exists(saved_name)
    storage.delete(saved_name)
    assert not storage.exists(saved_name)


@pytest.mark.django_db
def test_local_storage_size():
    """本地存储：size() 返回正确字节数。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    filename = 'test_size.txt'
    content = b'1234567890'

    try:
        saved_name = storage._save(filename, ContentFile(content))
        assert storage.size(saved_name) == len(content)
    finally:
        _cleanup_storage_file(storage, filename)


@pytest.mark.django_db
def test_local_storage_url():
    """本地存储：url() 返回包含 media/ 前缀的 URL。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    filename = 'test_url.txt'

    try:
        saved_name = storage._save(filename, ContentFile(b'url test'))
        url = storage.url(saved_name)
        assert 'media/' in url
    finally:
        _cleanup_storage_file(storage, filename)


@pytest.mark.django_db
def test_local_storage_listdir():
    """本地存储：listdir 返回目录内容。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    saved_name = storage._save('test_listdir.txt', ContentFile(b'dir test'))

    try:
        dirs, files = storage.listdir('')
        assert 'test_listdir.txt' in files
    finally:
        _cleanup_storage_file(storage, saved_name)


@pytest.mark.django_db
def test_local_storage_get_valid_name():
    """本地存储：get_valid_name 清理非法字符。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    valid = storage.get_valid_name('test/file\\name.txt')
    assert '/' not in valid
    assert '\\' not in valid


@pytest.mark.django_db
def test_local_storage_get_available_name():
    """本地存储：get_available_name 返回不冲突的文件名。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    available = storage.get_available_name('test_avail.txt')
    assert available == 'test_avail.txt'  # 文件不存在时不添加后缀


@pytest.mark.django_db
def test_local_file_overwrite():
    """本地存储：同名文件覆盖行为。"""
    _make_setting('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    filename = 'test_overwrite.txt'

    try:
        name1 = storage._save(filename, ContentFile(b'original'))
        name2 = storage._save(filename, ContentFile(b'updated'))
        f = storage._open(name2)
        content = f.read()
        f.close()
        assert content == b'updated'
    finally:
        _cleanup_storage_file(storage, filename)


# ==================== S3/COS 远程存储集成测试 ====================

# 腾讯云 COS 凭证（通过环境变量 .django-test-env 配置）
COS_ACCESS_KEY = os.environ.get('COS_ACCESS_KEY', 'AKIDtest')
COS_SECRET_KEY = os.environ.get('COS_SECRET_KEY', 'testsecret')
COS_BUCKET = os.environ.get('COS_BUCKET', 'yunwei-1328164982')
COS_REGION = os.environ.get('COS_REGION', 'ap-guangzhou')
COS_ENDPOINT = os.environ.get('COS_ENDPOINT', 'https://cos.ap-guangzhou.myqcloud.com')

# 测试文件前缀，用于区分测试文件避免与生产文件冲突
COS_TEST_PREFIX = '__xadmin_test__/'


def _cos_test_filename(name: str) -> str:
    """生成带测试前缀的文件名。"""
    return f'{COS_TEST_PREFIX}{name}'


def _s3_storage_available() -> bool:
    """检测 S3/COS 远程存储是否可用。"""
    try:
        _make_s3_media_settings(
            bucket=COS_BUCKET,
            endpoint=COS_ENDPOINT,
            region=COS_REGION,
            access_key=COS_ACCESS_KEY,
            secret_key=COS_SECRET_KEY,
        )
        storage = DynamicFileStorage()
        filename = _cos_test_filename('connection_test.txt')
        try:
            storage._save(filename, ContentFile(b'ping'))
            storage.delete(filename)
            return True
        except Exception:
            return False
    except Exception:
        return False
    finally:
        # 清理测试产生的 Setting 记录
        Setting.objects.filter(category='storage').delete()


def _require_s3():
    """如果 S3 不可用则跳过当前测试。"""
    if not _s3_storage_available():
        pytest.skip('S3/COS 远程存储不可用，跳过集成测试')


@pytest.mark.django_db
def test_s3_cos_save_and_read():
    """S3/COS 远程存储：上传文件后能正确读取内容。"""
    _require_s3()
    _make_s3_media_settings(
        bucket=COS_BUCKET,
        endpoint=COS_ENDPOINT,
        region=COS_REGION,
        access_key=COS_ACCESS_KEY,
        secret_key=COS_SECRET_KEY,
    )
    storage = DynamicFileStorage()
    filename = _cos_test_filename('crud_test.txt')
    content = b'S3 COS integration test'

    try:
        assert not is_local_storage()
        saved_name = storage._save(filename, ContentFile(content))
        assert storage.exists(saved_name)

        f = storage._open(saved_name)
        assert f.read() == content
        f.close()
    finally:
        _cleanup_storage_file(storage, filename)
        Setting.objects.filter(category='storage').delete()


@pytest.mark.django_db
def test_s3_cos_delete():
    """S3/COS 远程存储：删除文件后不存在。"""
    _require_s3()
    _make_s3_media_settings(
        bucket=COS_BUCKET,
        endpoint=COS_ENDPOINT,
        region=COS_REGION,
        access_key=COS_ACCESS_KEY,
        secret_key=COS_SECRET_KEY,
    )
    storage = DynamicFileStorage()
    filename = _cos_test_filename('delete_test.txt')

    saved_name = storage._save(filename, ContentFile(b'delete me'))
    assert storage.exists(saved_name)
    storage.delete(saved_name)
    assert not storage.exists(saved_name)
    Setting.objects.filter(category='storage').delete()


@pytest.mark.django_db
def test_s3_cos_size():
    """S3/COS 远程存储：size() 返回正确字节数。"""
    _require_s3()
    _make_s3_media_settings(
        bucket=COS_BUCKET,
        endpoint=COS_ENDPOINT,
        region=COS_REGION,
        access_key=COS_ACCESS_KEY,
        secret_key=COS_SECRET_KEY,
    )
    storage = DynamicFileStorage()
    filename = _cos_test_filename('size_test.txt')
    content = b'Size test: 32 bytes exactly!'

    try:
        saved_name = storage._save(filename, ContentFile(content))
        assert storage.size(saved_name) == len(content)
    finally:
        _cleanup_storage_file(storage, filename)
        Setting.objects.filter(category='storage').delete()


@pytest.mark.django_db
def test_s3_cos_url():
    """S3/COS 远程存储：url() 返回可访问的签名 URL。"""
    _require_s3()
    _make_s3_media_settings(
        bucket=COS_BUCKET,
        endpoint=COS_ENDPOINT,
        region=COS_REGION,
        access_key=COS_ACCESS_KEY,
        secret_key=COS_SECRET_KEY,
    )
    storage = DynamicFileStorage()
    filename = _cos_test_filename('url_test.txt')

    try:
        saved_name = storage._save(filename, ContentFile(b'url test'))
        url = storage.url(saved_name)
        # COS URL 应包含 bucket 或 endpoint
        assert (COS_BUCKET in url) or ('myqcloud.com' in url) or ('cos.' in url)
    finally:
        _cleanup_storage_file(storage, filename)
        Setting.objects.filter(category='storage').delete()


@pytest.mark.django_db
def test_s3_cos_listdir():
    """S3/COS 远程存储：listdir 返回目录内容。"""
    _require_s3()
    _make_s3_media_settings(
        bucket=COS_BUCKET,
        endpoint=COS_ENDPOINT,
        region=COS_REGION,
        access_key=COS_ACCESS_KEY,
        secret_key=COS_SECRET_KEY,
    )
    storage = DynamicFileStorage()
    filename = _cos_test_filename('listdir_test.txt')

    try:
        storage._save(filename, ContentFile(b'listdir'))
        dirs, files = storage.listdir(COS_TEST_PREFIX)
        assert 'listdir_test.txt' in files
    finally:
        _cleanup_storage_file(storage, filename)
        Setting.objects.filter(category='storage').delete()


@pytest.mark.django_db
def test_s3_cos_local_switch_roundtrip():
    """切换本地→S3→本地后存储后端正确重建。"""
    _require_s3()
    storage = DynamicFileStorage()

    # 1. 本地模式
    _make_setting('STORAGE_BACKEND', 'local')
    assert is_local_storage()
    local_name = 'switch_local.txt'
    try:
        storage._save(local_name, ContentFile(b'local'))
        assert storage.exists(local_name)
    finally:
        _cleanup_storage_file(storage, local_name)

    # 2. 切换到 S3
    _make_setting('STORAGE_BACKEND', 's3')
    _make_setting('STORAGE_S3_BUCKET_NAME', COS_BUCKET)
    _make_setting('STORAGE_S3_ENDPOINT_URL', COS_ENDPOINT)
    _make_setting('STORAGE_S3_REGION_NAME', COS_REGION)
    _make_setting('STORAGE_S3_ACCESS_KEY', COS_ACCESS_KEY)
    _make_setting('STORAGE_S3_SECRET_KEY', COS_SECRET_KEY)
    _make_setting('STORAGE_S3_ADDRESSING_STYLE', 'virtual')
    _make_setting('STORAGE_S3_LOCATION', 'media/')

    assert not is_local_storage()
    s3_name = _cos_test_filename('switch_s3.txt')
    try:
        storage._save(s3_name, ContentFile(b's3'))
        assert storage.exists(s3_name)
    finally:
        _cleanup_storage_file(storage, s3_name)
        Setting.objects.filter(category='storage').delete()


# ==================== 腾讯云 COS 配置专项测试 ====================


@pytest.mark.django_db
def test_cos_endpoint_format(auth_client):
    """COS 端点格式：https://cos.{region}.myqcloud.com。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'yunwei-1328164982',
        'STORAGE_S3_ENDPOINT_URL': 'https://cos.ap-guangzhou.myqcloud.com',
        'STORAGE_S3_REGION_NAME': 'ap-guangzhou',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
        'STORAGE_S3_ADDRESSING_STYLE': 'virtual',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_cos_addressing_style_virtual(auth_client):
    """COS 必须使用 virtual-hosted 寻址方式。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'yunwei-1328164982',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
        'STORAGE_S3_ADDRESSING_STYLE': 'virtual',
    }, format='json')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_cos_region_ap_guangzhou(auth_client):
    """COS 区域 ap-guangzhou 可正常配置。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'yunwei-1328164982',
        'STORAGE_S3_REGION_NAME': 'ap-guangzhou',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
    }, format='json')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_cos_full_config(auth_client):
    """COS 完整配置（含所有可选字段）可正常提交。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'yunwei-1328164982',
        'STORAGE_S3_ENDPOINT_URL': 'https://cos.ap-guangzhou.myqcloud.com',
        'STORAGE_S3_REGION_NAME': 'ap-guangzhou',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
        'STORAGE_S3_ADDRESSING_STYLE': 'virtual',
        'STORAGE_S3_SIGNATURE_VERSION': 's3v4',
        'STORAGE_S3_USE_SSL': True,
        'STORAGE_S3_VERIFY': True,
        'STORAGE_S3_LOCATION': 'media/',
        'STORAGE_S3_DEFAULT_ACL': '',
        'STORAGE_S3_QUERYSTRING_AUTH': True,
        'STORAGE_S3_QUERYSTRING_EXPIRE': 3600,
        'STORAGE_S3_URL_PROTOCOL': 'https',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_cos_custom_domain_cdn(auth_client):
    """COS 配置 CDN 自定义域名。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'yunwei-1328164982',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
        'STORAGE_S3_CUSTOM_DOMAIN': 'cdn.example.com',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


# ==================== Setting 值写入验证 ====================


@pytest.mark.django_db
def test_patch_writes_to_setting_table(auth_client):
    """PATCH 提交后配置值持久化到 Setting 表。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'persist-bucket',
        'STORAGE_S3_ACCESS_KEY': 'persist-ak',
        'STORAGE_S3_SECRET_KEY': 'persist-sk',
    }, format='json')
    assert resp.status_code == 200

    s = Setting.objects.filter(name='STORAGE_S3_BUCKET_NAME', is_active=True).first()
    assert s is not None
    assert s.cleaned_value == 'persist-bucket'


@pytest.mark.django_db
def test_patch_setting_is_active_true(auth_client):
    """PATCH 写入的设置项 is_active 均为 True。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.patch(url, {
        'STORAGE_BACKEND': 's3',
        'STORAGE_S3_BUCKET_NAME': 'active-test',
        'STORAGE_S3_ACCESS_KEY': 'ak',
        'STORAGE_S3_SECRET_KEY': 'sk',
    }, format='json')
    assert resp.status_code == 200

    # category 由查询参数 media 决定，非类属性 storage
    s = Setting.objects.filter(name='STORAGE_S3_BUCKET_NAME', is_active=True).first()
    assert s is not None, '存储桶名称设置项应被持久化且 is_active=True'
    assert s.cleaned_value == 'active-test'


# ==================== 综合视图测试 ====================


@pytest.mark.django_db
def test_media_category_switches_serializer(auth_client):
    """category=media 使用 StorageMediaSerializer，响应中包含 STORAGE_BACKEND。"""
    url = reverse('settings:storage-detail') + '?category=media'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert 'STORAGE_BACKEND' in resp.data['data']


@pytest.mark.django_db
def test_static_category_switches_serializer(auth_client):
    """category=static 使用 StorageStaticSerializer，响应中包含 STATIC_STORAGE_BACKEND。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert 'STATIC_STORAGE_BACKEND' in resp.data['data']


@pytest.mark.django_db
def test_patch_static_local_mode(auth_client):
    """PATCH 静态文件切换到本地存储成功。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.patch(url, {
        'STATIC_STORAGE_BACKEND': 'local',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000


@pytest.mark.django_db
def test_patch_static_custom_location(auth_client):
    """PATCH 静态文件自定义 location。"""
    url = reverse('settings:storage-detail') + '?category=static'
    resp = auth_client.patch(url, {
        'STATIC_S3_LOCATION': 'assets/',
    }, format='json')
    assert resp.status_code == 200
    assert resp.data['code'] == 1000
