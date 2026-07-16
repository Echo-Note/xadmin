"""同步器注册表 — 管理平台同步器的注册、查找与实例化。

通过 @register_syncer 装饰器注册各平台同步器类，
提供按 platform_type / name 匹配的查找和实例化能力。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)

# 全局同步器注册表：{platform_type: SyncerClass}
_syncer_registry: dict[str, type[BaseCloudSyncer]] = {}


def register_syncer(cls: type[BaseCloudSyncer]) -> type[BaseCloudSyncer]:
    """装饰器：将同步器类注册到全局注册表。

    每个平台同步器子类必须使用此装饰器，通过 PLATFORM_TYPE 标识自己。

    Usage:
        @register_syncer
        class TencentCloudSyncer(BaseCloudSyncer):
            PLATFORM_TYPE = "tencent"
            ...

    Args:
        cls: 同步器子类。

    Returns:
        原类，不做修改。
    """
    if cls.PLATFORM_TYPE:
        _syncer_registry[cls.PLATFORM_TYPE] = cls
        logger.debug('已注册同步器: %s -> %s', cls.PLATFORM_TYPE, cls.__name__)
    return cls


def get_syncer(platform_type: str) -> type[BaseCloudSyncer] | None:
    """根据平台类型获取已注册的同步器类。

    Args:
        platform_type: 平台类型标识（如 'tencent'/'aliyun'）。

    Returns:
        同步器类，未注册时返回 None。
    """
    return _syncer_registry.get(platform_type)


def get_all_syncers() -> dict[str, type[BaseCloudSyncer]]:
    """获取所有已注册的同步器。

    Returns:
        {platform_type: SyncerClass} 字典。
    """
    return dict(_syncer_registry)


def get_syncer_by_platform(cloud_platform) -> BaseCloudSyncer | None:  # noqa: ANN001
    """根据 CloudPlatform 实例获取对应的同步器实例。

    匹配优先级：
    1. platform_type 精确匹配
    2. name 精确匹配（大小写不敏感）
    3. name 子串包含匹配

    Args:
        cloud_platform: CloudPlatform 模型实例。

    Returns:
        同步器实例，未匹配到则返回 None。
    """
    platform_type = cloud_platform.platform_type
    platform_name = cloud_platform.name

    # 1. platform_type 精确匹配
    if platform_type and platform_type in _syncer_registry:
        return _syncer_registry[platform_type](cloud_platform)

    # 2. name 精确匹配
    name_lower = platform_name.lower().strip()
    for syncer_cls in _syncer_registry.values():
        for alias in getattr(syncer_cls, 'PLATFORM_NAMES', []):
            if alias.lower() == name_lower:
                return syncer_cls(cloud_platform)

    # 3. name 子串包含匹配
    for key, syncer_cls in _syncer_registry.items():
        if key in name_lower or name_lower in key:
            return syncer_cls(cloud_platform)

    return None
