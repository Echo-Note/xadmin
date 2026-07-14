"""存储设置序列化器 — 媒体文件与静态文件分离配置。

★ 前缀 = S3 模式下必填字段。
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

STORAGE_BACKEND_CHOICES = [
    ("local", _("本地文件存储")),
    ("s3", _("S3 兼容对象存储")),
]

GZIP_CONTENT_TYPE_CHOICES = [
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/x-javascript",
    "image/svg+xml",
    "text/html",
    "text/plain",
    "application/json",
    "application/xml",
]

S3_MEDIA_REQUIRED = ["STORAGE_S3_ACCESS_KEY", "STORAGE_S3_SECRET_KEY", "STORAGE_S3_BUCKET_NAME"]
S3_STATIC_REQUIRED = ["STATIC_S3_ACCESS_KEY", "STATIC_S3_SECRET_KEY", "STATIC_S3_BUCKET_NAME"]


def _validate_s3_required(attrs: dict, required_fields: list[str]) -> dict:
    """S3 模式下校验必填字段。"""
    backend = attrs.get("STORAGE_BACKEND") or attrs.get("STATIC_STORAGE_BACKEND")
    if backend != "s3":
        return attrs
    errors = {}
    for name in required_fields:
        value = attrs.get(name)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            errors[name] = _("S3 存储模式下此字段为必填项")
    if errors:
        raise serializers.ValidationError(errors)
    return attrs


# ==================== 媒体文件存储序列化器 ====================

class StorageMediaSerializer(serializers.Serializer):
    """媒体文件存储配置（用户上传的文件）。"""

    # 后端选择
    STORAGE_BACKEND = serializers.ChoiceField(
        choices=STORAGE_BACKEND_CHOICES, default="local",
        label=_("存储后端"),
        help_text=_("用户上传的媒体文件存储位置。本地 / S3 兼容对象存储。支持运行时切换。"),
    )

    # 存储桶
    STORAGE_S3_BUCKET_NAME = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("★ 存储桶名称 (Bucket)"),
        help_text=_("S3 模式必填。"),
    )
    STORAGE_S3_ENDPOINT_URL = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("端点 URL (Endpoint)"),
        help_text=_("AWS 留空；阿里云 https://oss-cn-hangzhou.aliyuncs.com；腾讯云 https://cos.ap-guangzhou.myqcloud.com；MinIO http://minio:9000"),
    )
    STORAGE_S3_REGION_NAME = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("区域 (Region)"),
        help_text=_("如 us-east-1、cn-hangzhou、ap-guangzhou。"),
    )

    # 认证
    STORAGE_S3_ACCESS_KEY = serializers.CharField(
        required=False, allow_blank=True, write_only=True, default="",
        label=_("★ 访问密钥 ID"),
        help_text=_("S3 模式必填。"),
    )
    STORAGE_S3_SECRET_KEY = serializers.CharField(
        required=False, allow_blank=True, write_only=True, default="",
        label=_("★ 访问密钥 Secret"),
        help_text=_("S3 模式必填。"),
    )

    # 连接
    STORAGE_S3_ADDRESSING_STYLE = serializers.ChoiceField(
        choices=[("path", _("Path-Style")), ("virtual", _("Virtual-Hosted"))],
        required=False, default="path",
        label=_("寻址方式"),
        help_text=_("Path-Style（MinIO/阿里云）/ Virtual-Hosted（AWS S3/腾讯云 COS）。"),
    )
    STORAGE_S3_SIGNATURE_VERSION = serializers.CharField(
        required=False, allow_blank=True, default="s3v4",
        label=_("签名版本"),
    )
    STORAGE_S3_USE_SSL = serializers.BooleanField(
        required=False, default=True, label=_("使用 SSL"),
    )
    STORAGE_S3_VERIFY = serializers.BooleanField(
        required=False, default=True, label=_("验证 SSL 证书"),
    )

    # URL
    STORAGE_S3_DEFAULT_ACL = serializers.ChoiceField(
        choices=[
            ("", _("私有（推荐）— 仅通过签名 URL 访问")),
            ("public-read", _("公开读 — 任何人可读取")),
            ("authenticated-read", _("认证读 — 仅 AWS 认证用户可读")),
            ("bucket-owner-full-control", _("桶 Owner 全控 — 跨账号写入场景")),
        ],
        required=False, allow_blank=True, default="",
        label=_("默认 ACL"),
        help_text=_("切勿使用 public-read-write。"),
    )
    STORAGE_S3_QUERYSTRING_AUTH = serializers.BooleanField(
        required=False, default=True, label=_("URL 签名认证"),
    )
    STORAGE_S3_QUERYSTRING_EXPIRE = serializers.IntegerField(
        required=False, default=3600, label=_("签名过期时间（秒）"),
    )
    STORAGE_S3_CUSTOM_DOMAIN = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("自定义域名 (CDN)"),
    )
    STORAGE_S3_URL_PROTOCOL = serializers.ChoiceField(
        choices=[("https", "https"), ("http", "http")],
        required=False, default="https",
        label=_("URL 协议"),
    )

    # 上传
    STORAGE_S3_FILE_OVERWRITE = serializers.BooleanField(
        required=False, default=True, label=_("同名文件覆盖"),
    )
    STORAGE_S3_LOCATION = serializers.CharField(
        required=False, allow_blank=True, default="media/",
        label=_("上传路径前缀"),
        help_text=_("文件在存储桶中的路径前缀，如 'media/'、'uploads/'。"),
    )
    STORAGE_S3_MAX_MEMORY_SIZE = serializers.IntegerField(
        required=False, default=5242880,
        label=_("内存上传上限（字节）"),
        help_text=_("小于此大小的文件直接在内存中上传，0 不限制。默认 5MB。"),
    )
    STORAGE_S3_GZIP = serializers.BooleanField(
        required=False, default=False, label=_("Gzip 压缩"),
    )
    STORAGE_S3_GZIP_CONTENT_TYPES = serializers.MultipleChoiceField(
        choices=[(t, t) for t in GZIP_CONTENT_TYPE_CHOICES],
        required=False, default=list,
        label=_("Gzip 压缩类型"),
        help_text=_("启用 Gzip 后需要压缩的 MIME 类型，可多选。"),
    )

    def validate(self, attrs: dict) -> dict:
        return _validate_s3_required(attrs, S3_MEDIA_REQUIRED)


# ==================== 静态文件存储序列化器 ====================

class StorageStaticSerializer(serializers.Serializer):
    """静态文件存储配置（CSS/JS/图片等 collectstatic 收集的文件）。

    未填写的 S3 配置项会自动回退到媒体文件存储的对应配置。
    """

    # 后端选择
    STATIC_STORAGE_BACKEND = serializers.ChoiceField(
        choices=STORAGE_BACKEND_CHOICES, default="local",
        label=_("存储后端"),
        help_text=_("CSS/JS/图片等静态文件存储位置。切换后需重启并重新执行 collectstatic。"),
    )

    # 独立 S3 配置（留空则回退到媒体文件配置）
    STATIC_S3_BUCKET_NAME = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("★ 存储桶名称（留空则复用媒体文件桶）"),
        help_text=_("S3 模式必填。通常与媒体文件共用同一桶，通过路径前缀区分。如需独立桶则填写。"),
    )
    STATIC_S3_ENDPOINT_URL = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("端点 URL（留空则复用媒体文件配置）"),
        help_text=_("通常与媒体文件相同端点。仅在静态文件使用不同 S3 服务时填写。"),
    )
    STATIC_S3_REGION_NAME = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("区域（留空则复用媒体文件配置）"),
    )
    STATIC_S3_ACCESS_KEY = serializers.CharField(
        required=False, allow_blank=True, write_only=True, default="",
        label=_("★ 访问密钥 ID（留空则复用媒体文件密钥）"),
        help_text=_("S3 模式必填。通常与媒体文件共用同一密钥。"),
    )
    STATIC_S3_SECRET_KEY = serializers.CharField(
        required=False, allow_blank=True, write_only=True, default="",
        label=_("★ 访问密钥 Secret（留空则复用媒体文件密钥）"),
        help_text=_("S3 模式必填。通常与媒体文件共用同一密钥。"),
    )
    STATIC_S3_CUSTOM_DOMAIN = serializers.CharField(
        required=False, allow_blank=True, default="",
        label=_("自定义域名/CDN（留空则复用媒体文件配置）"),
        help_text=_("静态文件通常通过 CDN 加速，可单独配置域名。"),
    )
    STATIC_S3_LOCATION = serializers.CharField(
        required=False, allow_blank=True, default="static",
        label=_("路径前缀"),
        help_text=_("静态文件在存储桶中的路径前缀，默认 'static'，与媒体文件分开存放。"),
    )

    def validate(self, attrs: dict) -> dict:
        return _validate_s3_required(attrs, S3_STATIC_REQUIRED)
