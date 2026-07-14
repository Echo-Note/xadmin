"""存储设置序列化器测试用例。"""
import pytest
from rest_framework.exceptions import ValidationError

from apps.settings.serializers.storage import (
    StorageMediaSerializer,
    StorageStaticSerializer,
)


class TestStorageMediaSerializer:
    """媒体文件存储序列化器测试。"""

    # ---- 本地存储模式 ----

    def test_local_default(self):
        """默认使用本地存储。"""
        s = StorageMediaSerializer(data={})
        assert s.is_valid()
        assert s.validated_data['STORAGE_BACKEND'] == 'local'

    def test_local_all_fields_optional(self):
        """本地模式下 S3 字段均可为空。"""
        s = StorageMediaSerializer(data={
            'STORAGE_BACKEND': 'local',
            'STORAGE_S3_BUCKET_NAME': '',
            'STORAGE_S3_ACCESS_KEY': '',
            'STORAGE_S3_SECRET_KEY': '',
        })
        assert s.is_valid()

    # ---- S3 模式校验 ----

    def test_s3_missing_bucket(self):
        """S3 模式下缺少 bucket_name 应校验失败。"""
        s = StorageMediaSerializer(data={
            'STORAGE_BACKEND': 's3',
            'STORAGE_S3_ACCESS_KEY': 'ak',
            'STORAGE_S3_SECRET_KEY': 'sk',
            'STORAGE_S3_BUCKET_NAME': '',
        })
        assert not s.is_valid()
        assert 'STORAGE_S3_BUCKET_NAME' in s.errors

    def test_s3_missing_access_key(self):
        """S3 模式下缺少 access_key 应校验失败。"""
        s = StorageMediaSerializer(data={
            'STORAGE_BACKEND': 's3',
            'STORAGE_S3_BUCKET_NAME': 'bucket',
            'STORAGE_S3_ACCESS_KEY': '',
            'STORAGE_S3_SECRET_KEY': 'sk',
        })
        assert not s.is_valid()
        assert 'STORAGE_S3_ACCESS_KEY' in s.errors

    def test_s3_missing_secret_key(self):
        """S3 模式下缺少 secret_key 应校验失败。"""
        s = StorageMediaSerializer(data={
            'STORAGE_BACKEND': 's3',
            'STORAGE_S3_BUCKET_NAME': 'bucket',
            'STORAGE_S3_ACCESS_KEY': 'ak',
            'STORAGE_S3_SECRET_KEY': '',
        })
        assert not s.is_valid()
        assert 'STORAGE_S3_SECRET_KEY' in s.errors

    def test_s3_valid_minimal(self):
        """S3 模式最小合法配置（仅必填字段）。"""
        s = StorageMediaSerializer(data={
            'STORAGE_BACKEND': 's3',
            'STORAGE_S3_BUCKET_NAME': 'my-bucket',
            'STORAGE_S3_ACCESS_KEY': 'AKIDxxx',
            'STORAGE_S3_SECRET_KEY': 'secretxxx',
        })
        assert s.is_valid()

    # ---- 默认值 ----

    def test_default_values(self):
        """验证各字段的默认值。"""
        s = StorageMediaSerializer(data={})
        assert s.is_valid()
        v = s.validated_data
        assert v['STORAGE_S3_ADDRESSING_STYLE'] == 'path'
        assert v['STORAGE_S3_SIGNATURE_VERSION'] == 's3v4'
        assert v['STORAGE_S3_USE_SSL'] is True
        assert v['STORAGE_S3_VERIFY'] is True
        assert v['STORAGE_S3_URL_PROTOCOL'] == 'https'
        assert v['STORAGE_S3_LOCATION'] == 'media/'
        assert v['STORAGE_S3_MAX_MEMORY_SIZE'] == 5242880
        assert v['STORAGE_S3_GZIP'] is False
        assert v['STORAGE_S3_GZIP_CONTENT_TYPES'] == []
        assert v['STORAGE_S3_QUERYSTRING_AUTH'] is True
        assert v['STORAGE_S3_QUERYSTRING_EXPIRE'] == 3600
        assert v['STORAGE_S3_FILE_OVERWRITE'] is True
        assert v['STORAGE_S3_DEFAULT_ACL'] == ''

    # ---- ACL 单选项 ----

    def test_acl_valid_choices(self):
        """ACL 下拉选项均合法。"""
        for acl in ['', 'public-read', 'authenticated-read', 'bucket-owner-full-control']:
            s = StorageMediaSerializer(data={
                'STORAGE_BACKEND': 'local',
                'STORAGE_S3_DEFAULT_ACL': acl,
            })
            assert s.is_valid(), f"ACL '{acl}' should be valid"

    def test_acl_invalid(self):
        """非法 ACL 值应被拒绝。"""
        s = StorageMediaSerializer(data={
            'STORAGE_BACKEND': 'local',
            'STORAGE_S3_DEFAULT_ACL': 'public-read-write',
        })
        assert not s.is_valid()

    # ---- URL 协议 ----

    def test_url_protocol_https(self):
        """URL 协议 https 合法。"""
        s = StorageMediaSerializer(data={'STORAGE_S3_URL_PROTOCOL': 'https'})
        assert s.is_valid()
        assert s.validated_data['STORAGE_S3_URL_PROTOCOL'] == 'https'

    def test_url_protocol_http(self):
        """URL 协议 http 合法。"""
        s = StorageMediaSerializer(data={'STORAGE_S3_URL_PROTOCOL': 'http'})
        assert s.is_valid()

    # ---- Gzip 类型多选 ----

    def test_gzip_content_types_empty(self):
        """Gzip 类型默认为空列表。"""
        s = StorageMediaSerializer(data={})
        assert s.is_valid()
        assert s.validated_data['STORAGE_S3_GZIP_CONTENT_TYPES'] == []

    def test_gzip_content_types_valid(self):
        """Gzip 类型多选合法值。"""
        s = StorageMediaSerializer(data={
            'STORAGE_S3_GZIP_CONTENT_TYPES': ['text/css', 'text/javascript']
        })
        assert s.is_valid()
        assert 'text/css' in s.validated_data['STORAGE_S3_GZIP_CONTENT_TYPES']

    def test_gzip_content_types_invalid(self):
        """非法 MIME 类型应被拒绝。"""
        s = StorageMediaSerializer(data={
            'STORAGE_S3_GZIP_CONTENT_TYPES': ['invalid/type']
        })
        assert not s.is_valid()

    # ---- 寻址方式 ----

    def test_addressing_style_valid(self):
        """Path-Style 和 Virtual-Hosted 均合法。"""
        for style in ['path', 'virtual']:
            s = StorageMediaSerializer(data={
                'STORAGE_S3_ADDRESSING_STYLE': style,
            })
            assert s.is_valid()


class TestStorageStaticSerializer:
    """静态文件存储序列化器测试。"""

    def test_local_default(self):
        """静态文件默认本地存储。"""
        s = StorageStaticSerializer(data={})
        assert s.is_valid()
        assert s.validated_data['STATIC_STORAGE_BACKEND'] == 'local'

    def test_location_default(self):
        """静态文件路径默认 'static'。"""
        s = StorageStaticSerializer(data={})
        assert s.is_valid()
        assert s.validated_data['STATIC_S3_LOCATION'] == 'static'

    def test_s3_missing_static_bucket(self):
        """S3 模式下静态文件缺少 bucket_name 且未配置回退时校验失败。"""
        s = StorageStaticSerializer(data={
            'STATIC_STORAGE_BACKEND': 's3',
            'STATIC_S3_ACCESS_KEY': 'ak',
            'STATIC_S3_SECRET_KEY': 'sk',
            'STATIC_S3_BUCKET_NAME': '',
        })
        assert not s.is_valid()

    def test_s3_valid_minimal(self):
        """S3 模式最小合法配置。"""
        s = StorageStaticSerializer(data={
            'STATIC_STORAGE_BACKEND': 's3',
            'STATIC_S3_BUCKET_NAME': 'static-bucket',
            'STATIC_S3_ACCESS_KEY': 'ak',
            'STATIC_S3_SECRET_KEY': 'sk',
        })
        assert s.is_valid()
