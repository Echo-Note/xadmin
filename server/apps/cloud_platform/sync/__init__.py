"""云平台资源同步模块。

通过 BaseCloudSyncer 抽象基类定义统一的同步流程，各平台子类实现具体的 API 调用逻辑。
所有数据库交互使用序列化器，保证数据校验和幂等性。

Usage:
    from apps.cloud_platform.sync import SyncEngine

    engine = SyncEngine()
    engine.run(cloud_platform, sync_type='manual', resources=['server', 'domain'])
"""

# 触发 @register_syncer 装饰器注册所有同步器
from apps.cloud_platform.sync import (
    aliyun,  # noqa: F401
    huawei,  # noqa: F401
    meicheng,  # noqa: F401
    tencent,  # noqa: F401
    vsphere,  # noqa: F401
)
from apps.cloud_platform.sync.engine import SyncEngine, get_all_syncers, get_syncer, get_syncer_by_platform
from apps.cloud_platform.sync.schemas import (
    BalanceSyncData,
    DnsRecordSyncData,
    DomainSyncData,
    ServerSyncData,
    SyncResult,
)

__all__ = [
    'SyncEngine',
    'get_syncer',
    'get_syncer_by_platform',
    'get_all_syncers',
    'ServerSyncData',
    'DomainSyncData',
    'DnsRecordSyncData',
    'BalanceSyncData',
    'SyncResult',
]
