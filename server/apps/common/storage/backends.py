"""动态文件存储后端，支持本地存储与 S3 兼容对象存储的运行时切换。

读取数据库中的存储配置项来决定实际使用的存储后端。切换存储后端后，
已有的旧文件需要手动迁移。
"""

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import caches
from django.core.files.storage import FileSystemStorage
from django.utils.functional import cached_property

if TYPE_CHECKING:
    from django.core.files.storage import Storage

logger = logging.getLogger(__name__)

# 存储配置切换版本键名，配置变更时自增以强制重建后端实例
STORAGE_CONFIG_VERSION_KEY = "STORAGE_CONFIG_VERSION"


def _get_storage_setting(name: str, default: Any = None) -> Any:
    """从数据库 Setting 表读取存储配置项。

    优先读数据库，不存在时回退到 Django settings 中的默认值。

    Args:
        name: 配置项名称。
        default: 数据库不存在时的回退默认值。

    Returns:
        配置值。
    """
    try:
        from apps.settings.models import Setting  # 延迟导入，避免循环依赖

        obj = Setting.objects.filter(name=name, is_active=True).first()
        if obj and obj.cleaned_value is not None:
            return obj.cleaned_value
    except Exception:
        logger.warning("读取存储配置 %s 失败，回退到默认值", name, exc_info=True)
    return getattr(settings, name, default)


def is_local_storage() -> bool:
    """检查当前是否使用本地文件存储。

    Returns:
        True 表示使用本地文件存储，False 表示使用远程 S3 存储。
    """
    backend = _get_storage_setting("STORAGE_BACKEND", "local")
    return backend == "local"


class DynamicFileStorage:
    """动态文件存储后端，根据数据库配置路由到本地或 S3 存储。

    用法：
        在 Django ``STORAGES`` 设置的 ``default`` 后端中使用此类：:

            STORAGES = {
                "default": {
                    "BACKEND": "apps.common.storage.backends.DynamicFileStorage",
                },
                ...
            }

    配置项（存储在 Setting 模型中）：
        - STORAGE_BACKEND: "local" 或 "s3"
        - STORAGE_S3_ENDPOINT_URL: S3 兼容端点 URL
        - STORAGE_S3_ACCESS_KEY: 访问密钥 ID
        - STORAGE_S3_SECRET_KEY: 访问密钥 Secret
        - STORAGE_S3_BUCKET_NAME: 存储桶名称
        - STORAGE_S3_REGION_NAME: 区域（可选）
        - STORAGE_S3_USE_SSL: 是否使用 SSL（默认 True）
        - STORAGE_S3_VERIFY: 是否验证 SSL 证书（默认 True）
        - STORAGE_S3_SIGNATURE_VERSION: 签名版本（默认 s3v4）
        - STORAGE_S3_CUSTOM_DOMAIN: 自定义域名/CDN 加速域名（可选）
        - STORAGE_S3_DEFAULT_ACL: 默认 ACL
        - STORAGE_S3_QUERYSTRING_AUTH: 是否对 URL 签名认证
        - STORAGE_S3_QUERYSTRING_EXPIRE: 签名 URL 过期秒数
        - STORAGE_S3_FILE_OVERWRITE: 同名文件是否覆盖
        - STORAGE_S3_LOCATION: 上传路径前缀
        - STORAGE_S3_URL_PROTOCOL: URL 协议（如 "https:"）
        - STORAGE_S3_MAX_MEMORY_SIZE: 内存中文件最大字节数
        - STORAGE_S3_ADDRESSING_STYLE: 寻址方式（"path" 或 "virtual"）
        - STORAGE_S3_GZIP: 是否对文本文件启用 Gzip 压缩（默认 False）
        - STORAGE_S3_GZIP_CONTENT_TYPES: 需要 Gzip 压缩的 MIME 类型（逗号分隔）

        不同云厂商推荐：
        - MinIO / 阿里云 OSS: addressing_style="path"
        - 腾讯云 COS: addressing_style="virtual"
        - AWS S3: addressing_style="virtual"（或不设置，boto3 自动选择）
    """

    # 存储配置项名称与构造函数参数的映射
    S3_CONFIG_MAP: dict[str, str] = {
        "STORAGE_S3_ENDPOINT_URL": "endpoint_url",
        "STORAGE_S3_ACCESS_KEY": "access_key",
        "STORAGE_S3_SECRET_KEY": "secret_key",
        "STORAGE_S3_BUCKET_NAME": "bucket_name",
        "STORAGE_S3_REGION_NAME": "region_name",
        "STORAGE_S3_USE_SSL": "use_ssl",
        "STORAGE_S3_VERIFY": "verify",
        "STORAGE_S3_SIGNATURE_VERSION": "signature_version",
        "STORAGE_S3_ADDRESSING_STYLE": "addressing_style",
        "STORAGE_S3_CUSTOM_DOMAIN": "custom_domain",
        "STORAGE_S3_DEFAULT_ACL": "default_acl",
        "STORAGE_S3_QUERYSTRING_AUTH": "querystring_auth",
        "STORAGE_S3_QUERYSTRING_EXPIRE": "querystring_expire",
        "STORAGE_S3_FILE_OVERWRITE": "file_overwrite",
        "STORAGE_S3_LOCATION": "location",
        "STORAGE_S3_URL_PROTOCOL": "url_protocol",
        "STORAGE_S3_MAX_MEMORY_SIZE": "max_memory_size",
        "STORAGE_S3_GZIP": "gzip",
        "STORAGE_S3_GZIP_CONTENT_TYPES": "gzip_content_types",
    }

    def __init__(self, **kwargs: Any) -> None:
        """初始化动态存储后端。"""
        super().__init__(**kwargs)  # type: ignore[call-arg]
        self._local_storage: FileSystemStorage | None = None
        self._s3_storage: "Storage | None" = None
        self._config_version: int = -1

    def _get_config_version(self) -> int:
        """获取当前存储配置版本号，用于检测配置是否变更。

        Returns:
            配置版本号。
        """
        try:
            cache = caches["default"]
            version = cache.get(
                settings.CACHE_KEY_TEMPLATE["config_key"] + ":storage_version"
            )
            if version is not None:
                return int(version)
        except Exception:
            pass
        return _get_storage_setting(STORAGE_CONFIG_VERSION_KEY, 0)

    def _ensure_backend(self) -> "Storage":
        """确保后端实例与当前配置一致，配置变更时重建 S3 后端。

        Returns:
            当前的存储后端实例。
        """
        if is_local_storage():
            if self._local_storage is None:
                self._local_storage = FileSystemStorage(
                    location=settings.MEDIA_ROOT,
                    base_url=settings.MEDIA_URL,
                )
            return self._local_storage

        # S3 后端：检查配置版本是否变更
        current_version = self._get_config_version()
        if self._s3_storage is None or current_version != self._config_version:
            self._s3_storage = self._build_s3_storage()
            self._config_version = current_version
            logger.info("S3 存储后端已创建/重建，配置版本: %s", current_version)
        return self._s3_storage

    def _build_s3_storage(self) -> "Storage":
        """根据数据库配置构建 S3 存储后端实例。

        Returns:
            配置好的 S3Boto3Storage 实例。
        """
        S3Storage = self._import_s3_storage()

        kwargs = build_s3_kwargs()
        logger.debug("创建 S3 存储后端，参数: endpoint_url=%s, bucket=%s, region=%s",
                      kwargs.get("endpoint_url"),
                      kwargs.get("bucket_name"),
                      kwargs.get("region_name"))
        return S3Storage(**kwargs)

    @staticmethod
    def _import_s3_storage() -> type:
        """兼容 django-storages 不同版本的类名。

        django-storages >=1.14 使用 ``S3Storage``，
        旧版本使用 ``S3Boto3Storage``。
        """
        from storages.backends import s3 as s3_module
        for name in ('S3Storage', 'S3Boto3Storage'):
            cls = getattr(s3_module, name, None)
            if cls is not None:
                return cls
        raise ImportError("无法从 storages.backends.s3 导入 S3Storage / S3Boto3Storage")

    # ---- 委托方法 ----

    def _open(self, name: str, mode: str = "rb") -> Any:
        """打开文件。

        Args:
            name: 文件名。
            mode: 打开模式。

        Returns:
            文件对象。
        """
        return self._ensure_backend()._open(name, mode)

    def save(self, name: str, content: Any, max_length: int | None = None) -> str:
        """保存文件（符合 Django Storage API）。

        Args:
            name: 文件名。
            content: 文件内容。
            max_length: 文件名最大长度。

        Returns:
            保存后的文件名。
        """
        name = self.get_available_name(name, max_length=max_length)
        return self._save(name, content)

    def _save(self, name: str, content: Any) -> str:
        """保存文件。

        Args:
            name: 文件名。
            content: 文件内容。

        Returns:
            保存后的文件名。
        """
        return self._ensure_backend()._save(name, content)

    def delete(self, name: str) -> None:
        """删除文件。

        Args:
            name: 文件名。
        """
        self._ensure_backend().delete(name)

    def exists(self, name: str) -> bool:
        """检查文件是否存在。

        Args:
            name: 文件名。

        Returns:
            True 表示文件存在。
        """
        return self._ensure_backend().exists(name)

    def listdir(self, path: str) -> tuple[list[str], list[str]]:
        """列出目录内容。

        Args:
            path: 目录路径。

        Returns:
            (目录列表, 文件列表) 元组。
        """
        return self._ensure_backend().listdir(path)

    def size(self, name: str) -> int:
        """获取文件大小。

        Args:
            name: 文件名。

        Returns:
            文件大小（字节）。
        """
        return self._ensure_backend().size(name)

    def url(self, name: str) -> str:
        """获取文件访问 URL。

        Args:
            name: 文件名。

        Returns:
            文件 URL。
        """
        return self._ensure_backend().url(name)

    def get_accessed_time(self, name: str) -> Any:
        """获取文件最后访问时间。

        Args:
            name: 文件名。

        Returns:
            访问时间。
        """
        return self._ensure_backend().get_accessed_time(name)

    def get_created_time(self, name: str) -> Any:
        """获取文件创建时间。

        Args:
            name: 文件名。

        Returns:
            创建时间。
        """
        return self._ensure_backend().get_created_time(name)

    def get_modified_time(self, name: str) -> Any:
        """获取文件最后修改时间。

        Args:
            name: 文件名。

        Returns:
            修改时间。
        """
        return self._ensure_backend().get_modified_time(name)

    def path(self, name: str) -> str:
        """获取文件本地路径（仅本地存储可用）。

        Args:
            name: 文件名。

        Returns:
            文件系统路径。
        """
        return self._ensure_backend().path(name)

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        """获取不冲突的可用文件名。

        Args:
            name: 原始文件名。
            max_length: 最大长度。

        Returns:
            不冲突的文件名。
        """
        return self._ensure_backend().get_available_name(name, max_length)

    def generate_filename(self, filename: str) -> str:
        """生成最终存储文件名。

        Args:
            filename: 原始文件名。

        Returns:
            处理后的文件名。
        """
        return self._ensure_backend().generate_filename(filename)

    def get_valid_name(self, name: str) -> str:
        """获取合法的文件名。

        Args:
            name: 原始文件名。

        Returns:
            合法文件名。
        """
        return self._ensure_backend().get_valid_name(name)

    # ---- 属性委托 ----

    @cached_property
    def base_location(self) -> str:
        """存储基础路径。"""
        return self._ensure_backend().base_location

    @cached_property
    def location(self) -> str:
        """存储位置。"""
        return self._ensure_backend().location

    @cached_property
    def base_url(self) -> str:
        """存储基础 URL。"""
        return self._ensure_backend().base_url

    @cached_property
    def file_permissions_mode(self) -> int | None:
        """文件权限模式。"""
        backend = self._ensure_backend()
        return getattr(backend, 'file_permissions_mode', None)

    @cached_property
    def directory_permissions_mode(self) -> int | None:
        """目录权限模式。"""
        backend = self._ensure_backend()
        return getattr(backend, 'directory_permissions_mode', None)


def build_s3_kwargs(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """从数据库读取 S3 配置并构建 S3Boto3Storage 构造函数参数。

    供 DynamicFileStorage 和 StaticS3Storage 共用。

    Args:
        overrides: 需要覆写的参数（如 location、default_acl），
                   用于静态文件存储等不同场景。

    Returns:
        S3Boto3Storage 构造函数参数字典。
    """
    kwargs: dict[str, Any] = {}
    for setting_name, kwarg_name in DynamicFileStorage.S3_CONFIG_MAP.items():
        value = _get_storage_setting(setting_name)
        if value is not None and value != "":
            kwargs[kwarg_name] = value

    kwargs.setdefault("signature_version", "s3v4")

    # gzip_content_types: 列表 → 元组（空列表则移除）
    if "gzip_content_types" in kwargs and isinstance(kwargs["gzip_content_types"], list):
        if kwargs["gzip_content_types"]:
            kwargs["gzip_content_types"] = tuple(kwargs["gzip_content_types"])
        else:
            del kwargs["gzip_content_types"]

    # url_protocol: 确保以 ":" 结尾
    if "url_protocol" in kwargs and isinstance(kwargs["url_protocol"], str):
        if not kwargs["url_protocol"].endswith(":"):
            kwargs["url_protocol"] += ":"

    # 应用覆写
    if overrides:
        kwargs.update(overrides)

    return kwargs


class StaticS3Storage:
    """静态文件 S3 存储后端。

    在启动时一次性读取 S3 配置并固定不变（静态文件在 ``collectstatic`` 时上传）。

    配置读取规则（独立配置 + 回退）：
        - 优先读取 ``STATIC_S3_*`` 配置项
        - 未填写则回退到 ``STORAGE_S3_*``（媒体文件配置）

    默认覆盖（相比媒体文件存储）：
        - default_acl = 'public-read'（静态文件需公开访问）
        - querystring_auth = False（不需要签名 URL）
        - file_overwrite = True（collectstatic 时覆盖）
        - location = 'static'（与媒体文件分开存储）

    用法：
        STORAGES = {
            "staticfiles": {
                "BACKEND": "apps.common.storage.backends.StaticS3Storage",
            },
        }
    """

    # STATIC_S3_* → STORAGE_S3_* 回退映射（仅需要独立配置的核心字段）
    STATIC_FALLBACK_MAP: dict[str, str] = {
        "STATIC_S3_BUCKET_NAME": "STORAGE_S3_BUCKET_NAME",
        "STATIC_S3_ENDPOINT_URL": "STORAGE_S3_ENDPOINT_URL",
        "STATIC_S3_ACCESS_KEY": "STORAGE_S3_ACCESS_KEY",
        "STATIC_S3_SECRET_KEY": "STORAGE_S3_SECRET_KEY",
        "STATIC_S3_REGION_NAME": "STORAGE_S3_REGION_NAME",
        "STATIC_S3_CUSTOM_DOMAIN": "STORAGE_S3_CUSTOM_DOMAIN",
    }

    def __init__(self, **kwargs: Any) -> None:
        """初始化静态文件 S3 存储。

        优先读取 STATIC_S3_* 配置，未填写则回退到 STORAGE_S3_*。
        其他通用设置（SSL、签名等）复用媒体文件配置。

        Args:
            **kwargs: 额外的 S3Boto3Storage 构造参数。
        """
        S3Storage = DynamicFileStorage._import_s3_storage()

        # 基础 S3 连接参数：优先 STATIC_S3_*，回退 STORAGE_S3_*
        s3_kwargs: dict[str, Any] = {}
        for static_name, media_name in self.STATIC_FALLBACK_MAP.items():
            value = _get_storage_setting(static_name)
            if not value or (isinstance(value, str) and not value.strip()):
                value = _get_storage_setting(media_name)
            if value is not None and value != "":
                kwarg_name = DynamicFileStorage.S3_CONFIG_MAP.get(media_name)
                if kwarg_name:
                    s3_kwargs[kwarg_name] = value

        # 位置前缀：优先 STATIC_S3_LOCATION，默认 "static"
        s3_kwargs["location"] = _get_storage_setting("STATIC_S3_LOCATION", "static")

        # 通用连接参数复用媒体文件配置
        for name in ("signature_version", "use_ssl", "verify", "addressing_style", "url_protocol"):
            setting_name = f"STORAGE_S3_{name.upper()}"
            value = _get_storage_setting(setting_name)
            if value is not None and value != "":
                s3_kwargs[name] = value

        s3_kwargs.setdefault("signature_version", "s3v4")

        # gzip 复用媒体文件配置
        gzip = _get_storage_setting("STORAGE_S3_GZIP")
        if gzip:
            s3_kwargs["gzip"] = True
            gzip_types = _get_storage_setting("STORAGE_S3_GZIP_CONTENT_TYPES")
            if gzip_types and isinstance(gzip_types, str):
                parsed = tuple(t.strip() for t in gzip_types.split(",") if t.strip())
                if parsed:
                    s3_kwargs["gzip_content_types"] = parsed

        # 静态文件专用覆盖
        s3_kwargs["default_acl"] = "public-read"
        s3_kwargs["querystring_auth"] = False
        s3_kwargs["file_overwrite"] = True

        s3_kwargs.update(kwargs)
        self._storage = S3Storage(**s3_kwargs)
        logger.info("StaticS3Storage 已初始化，bucket=%s, location=%s, endpoint=%s",
                     s3_kwargs.get("bucket_name"),
                     s3_kwargs.get("location"),
                     s3_kwargs.get("endpoint_url"))

    # ---- 委托到 S3Boto3Storage ----

    def _open(self, name: str, mode: str = "rb") -> Any:
        return self._storage._open(name, mode)

    def _save(self, name: str, content: Any) -> str:
        return self._storage._save(name, content)

    def delete(self, name: str) -> None:
        self._storage.delete(name)

    def exists(self, name: str) -> bool:
        return self._storage.exists(name)

    def listdir(self, path: str) -> tuple[list[str], list[str]]:
        return self._storage.listdir(path)

    def size(self, name: str) -> int:
        return self._storage.size(name)

    def url(self, name: str) -> str:
        return self._storage.url(name)

    def get_accessed_time(self, name: str) -> Any:
        return self._storage.get_accessed_time(name)

    def get_created_time(self, name: str) -> Any:
        return self._storage.get_created_time(name)

    def get_modified_time(self, name: str) -> Any:
        return self._storage.get_modified_time(name)

    def path(self, name: str) -> str:
        return self._storage.path(name)

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        return self._storage.get_available_name(name, max_length)

    def generate_filename(self, filename: str) -> str:
        return self._storage.generate_filename(filename)

    def get_valid_name(self, name: str) -> str:
        return self._storage.get_valid_name(name)

    @cached_property
    def base_location(self) -> str:
        return self._storage.base_location

    @cached_property
    def location(self) -> str:
        return self._storage.location

    @cached_property
    def base_url(self) -> str:
        return self._storage.base_url
