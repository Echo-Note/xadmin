"""解析器模块 — 将平台原始数据映射为内部统一标识。

包含状态解析、OS 类型解析、DNS 归属判断等映射逻辑，
避免硬编码映射表散布在业务代码中。
"""

from apps.cloud_platform.sync.resolvers.status_resolver import StatusResolver
from apps.cloud_platform.sync.resolvers.os_resolver import OSResolver
from apps.cloud_platform.sync.resolvers.dns_resolver import DNSResolver
from apps.cloud_platform.sync.resolvers.region_resolver import RegionResolver

__all__ = [
    'StatusResolver',
    'OSResolver',
    'DNSResolver',
    'RegionResolver',
]
