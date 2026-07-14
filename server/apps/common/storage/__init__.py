"""动态文件存储模块，支持本地文件系统与 S3 兼容对象存储的运行时切换。"""
from apps.common.storage.backends import DynamicFileStorage, StaticS3Storage, is_local_storage

__all__ = ["DynamicFileStorage", "StaticS3Storage", "is_local_storage"]
