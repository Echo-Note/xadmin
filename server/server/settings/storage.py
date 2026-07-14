"""存储设置模块，配置 Django STORAGES 及默认存储参数。

通过 CONFIG 读取初始配置，运行时可通过数据库 Setting 模型动态切换。
"""

from ..const import CONFIG, PROJECT_DIR
from pathlib import Path

# ==================== 存储后端选择 ====================
# "local" — 本地文件系统存储
# "s3"   — S3 兼容对象存储（AWS S3 / 阿里云 OSS / 腾讯云 COS / MinIO 等）
STORAGE_BACKEND = CONFIG.STORAGE_BACKEND

# ==================== 静态文件存储 ====================
# "local" — Django 本地 StaticFilesStorage（默认）
# "s3"   — S3 存储（public-read，无签名 URL，collectstatic 时上传）
STATIC_STORAGE_BACKEND = CONFIG.STATIC_STORAGE_BACKEND

# 静态文件独立 S3 配置（留空则运行时回退到 STORAGE_S3_*）
STATIC_S3_BUCKET_NAME = CONFIG.STATIC_S3_BUCKET_NAME
STATIC_S3_ENDPOINT_URL = CONFIG.STATIC_S3_ENDPOINT_URL
STATIC_S3_ACCESS_KEY = CONFIG.STATIC_S3_ACCESS_KEY
STATIC_S3_SECRET_KEY = CONFIG.STATIC_S3_SECRET_KEY
STATIC_S3_REGION_NAME = CONFIG.STATIC_S3_REGION_NAME
STATIC_S3_CUSTOM_DOMAIN = CONFIG.STATIC_S3_CUSTOM_DOMAIN
STATIC_S3_LOCATION = CONFIG.STATIC_S3_LOCATION

# ==================== Django STORAGES 配置 ====================
# default：使用 DynamicFileStorage，支持运行时切换本地/远程
# staticfiles：根据 STATIC_STORAGE_BACKEND 选择本地或 S3
STORAGES = {
    "default": {
        "BACKEND": "apps.common.storage.backends.DynamicFileStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "apps.common.storage.backends.StaticS3Storage"
            if STATIC_STORAGE_BACKEND == "s3"
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# ==================== S3 兼容存储默认配置 ====================
# 以下配置项在 storage_backend 为 "s3" 时生效，
# 运行时可被数据库中同名 Setting 覆盖

# S3 兼容端点 URL（不同云厂商填入不同地址）
# AWS S3（默认）: 留空，自动使用 AWS 默认端点
# 阿里云 OSS:    https://oss-{region}.aliyuncs.com
# 腾讯云 COS:    https://cos.{region}.myqcloud.com
# MinIO:         http://minio:9000
STORAGE_S3_ENDPOINT_URL = CONFIG.STORAGE_S3_ENDPOINT_URL
STORAGE_S3_ACCESS_KEY = CONFIG.STORAGE_S3_ACCESS_KEY
STORAGE_S3_SECRET_KEY = CONFIG.STORAGE_S3_SECRET_KEY
STORAGE_S3_BUCKET_NAME = CONFIG.STORAGE_S3_BUCKET_NAME
STORAGE_S3_REGION_NAME = CONFIG.STORAGE_S3_REGION_NAME
STORAGE_S3_USE_SSL = CONFIG.STORAGE_S3_USE_SSL
STORAGE_S3_VERIFY = CONFIG.STORAGE_S3_VERIFY
STORAGE_S3_SIGNATURE_VERSION = CONFIG.STORAGE_S3_SIGNATURE_VERSION
STORAGE_S3_ADDRESSING_STYLE = CONFIG.STORAGE_S3_ADDRESSING_STYLE
STORAGE_S3_CUSTOM_DOMAIN = CONFIG.STORAGE_S3_CUSTOM_DOMAIN
STORAGE_S3_DEFAULT_ACL = CONFIG.STORAGE_S3_DEFAULT_ACL
STORAGE_S3_QUERYSTRING_AUTH = CONFIG.STORAGE_S3_QUERYSTRING_AUTH
STORAGE_S3_QUERYSTRING_EXPIRE = CONFIG.STORAGE_S3_QUERYSTRING_EXPIRE
STORAGE_S3_FILE_OVERWRITE = CONFIG.STORAGE_S3_FILE_OVERWRITE
STORAGE_S3_LOCATION = CONFIG.STORAGE_S3_LOCATION
STORAGE_S3_URL_PROTOCOL = CONFIG.STORAGE_S3_URL_PROTOCOL
STORAGE_S3_MAX_MEMORY_SIZE = CONFIG.STORAGE_S3_MAX_MEMORY_SIZE
STORAGE_S3_GZIP = CONFIG.STORAGE_S3_GZIP
STORAGE_S3_GZIP_CONTENT_TYPES = CONFIG.STORAGE_S3_GZIP_CONTENT_TYPES  # list

# 存储配置版本号，变更时自增以强制重建 S3 连接
STORAGE_CONFIG_VERSION = CONFIG.STORAGE_CONFIG_VERSION

# ==================== 兼容旧代码的 MEDIA 配置 ====================
# 保留 MEDIA_ROOT / MEDIA_URL 以兼容可能直接引用这些配置的代码
DATA_DIR = Path(PROJECT_DIR) / "data"
MEDIA_URL = "media/"
MEDIA_ROOT = str(DATA_DIR / "upload")
