"""动态存储后端测试用例。"""
import json

import pytest
from django.core.files.storage import FileSystemStorage

from apps.common.storage.backends import (
    DynamicFileStorage,
    StaticS3Storage,
    build_s3_kwargs,
    is_local_storage,
)
from apps.common.storage import is_local_storage as is_local_storage_pkg
from apps.settings.models import Setting


def _make(name, value):
    Setting.objects.create(name=name, value=json.dumps(value), category='storage')


# ========== is_local_storage ==========

@pytest.mark.django_db
def test_default_is_local():
    assert is_local_storage() is True
    assert is_local_storage_pkg() is True


@pytest.mark.django_db
def test_local_storage_explicit():
    _make('STORAGE_BACKEND', 'local')
    assert is_local_storage() is True


@pytest.mark.django_db
def test_s3_is_not_local():
    _make('STORAGE_BACKEND', 's3')
    assert is_local_storage() is False


# ========== DynamicFileStorage ==========

@pytest.mark.django_db
def test_dynamic_file_operations():
    """本地模式下的文件 CRUD 操作。"""
    _make('STORAGE_BACKEND', 'local')
    storage = DynamicFileStorage()
    assert isinstance(storage._ensure_backend(), FileSystemStorage)

    from django.core.files.base import ContentFile
    name = storage._save('test.txt', ContentFile(b'hello'))
    assert storage.exists(name) is True
    f = storage._open(name)
    assert f.read() == b'hello'
    f.close()
    storage.delete(name)
    assert storage.exists(name) is False


# ========== StaticS3Storage ==========

@pytest.mark.django_db
def test_static_fallback_to_media():
    _make('STORAGE_S3_BUCKET_NAME', 'media-bucket')
    _make('STORAGE_S3_ACCESS_KEY', 'ak')
    _make('STORAGE_S3_SECRET_KEY', 'sk')
    s = StaticS3Storage()
    assert s._storage.bucket_name == 'media-bucket'
    assert s._storage.default_acl == 'public-read'
    assert s._storage.querystring_auth is False


@pytest.mark.django_db
def test_static_independent_bucket():
    _make('STORAGE_S3_BUCKET_NAME', 'media-bucket')
    _make('STORAGE_S3_ACCESS_KEY', 'ak')
    _make('STORAGE_S3_SECRET_KEY', 'sk')
    _make('STATIC_S3_BUCKET_NAME', 'static-bucket')
    assert StaticS3Storage()._storage.bucket_name == 'static-bucket'


@pytest.mark.django_db
def test_static_custom_location():
    _make('STORAGE_S3_BUCKET_NAME', 'bucket')
    _make('STORAGE_S3_ACCESS_KEY', 'ak')
    _make('STORAGE_S3_SECRET_KEY', 'sk')
    _make('STATIC_S3_LOCATION', 'assets')
    assert StaticS3Storage()._storage.location == 'assets'


# ========== build_s3_kwargs ==========

@pytest.mark.django_db
def test_kwargs_url_protocol_colon():
    _make('STORAGE_S3_URL_PROTOCOL', 'http')
    assert build_s3_kwargs()['url_protocol'] == 'http:'


@pytest.mark.django_db
def test_kwargs_gzip_conversion():
    _make('STORAGE_S3_GZIP_CONTENT_TYPES', ['text/css'])
    assert build_s3_kwargs()['gzip_content_types'] == ('text/css',)


@pytest.mark.django_db
def test_kwargs_empty_gzip_removed():
    _make('STORAGE_S3_GZIP_CONTENT_TYPES', [])
    assert 'gzip_content_types' not in build_s3_kwargs()


@pytest.mark.django_db
def test_kwargs_overrides():
    _make('STORAGE_S3_LOCATION', 'media/')
    kwargs = build_s3_kwargs(overrides={'location': 'static'})
    assert kwargs['location'] == 'static'
