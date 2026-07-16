"""云平台资源同步模块 — 多平台、多 Agent 并行同步架构。

架构分层：
- platforms/ : 平台数据拉取层（纯 API 调用，返回 Pydantic 模型）
- agents/    : Agent 执行层（持有 Serializer，负责拉取→校验→写入）
- serializers/: 序列化器层（封装所有数据库 ORM 操作）
- resolvers/ : 解析器层（状态/OS/DNS/区域映射）
- engine.py  : 同步引擎（多 Agent 并行调度 + 结果聚合）
- registry.py: 同步器注册表
- schemas.py : Pydantic 数据协议
- exceptions.py: 自定义异常

Usage:
    from apps.cloud_platform.sync import SyncEngine

    engine = SyncEngine()
    engine.run(cloud_platform, sync_type='manual', resources=['server', 'domain'])
"""

# 延迟加载平台同步器（在首次使用时通过 _ensure_platforms_loaded 触发）
_platforms_loaded = False


def _ensure_platforms_loaded() -> None:
    """延迟加载所有平台同步器，触发 @register_syncer 装饰器注册。"""
    global _platforms_loaded
    if _platforms_loaded:
        return
    # 导入平台模块以触发注册
    import apps.cloud_platform.sync.platforms.aliyun  # noqa: F401
    import apps.cloud_platform.sync.platforms.huawei  # noqa: F401
    import apps.cloud_platform.sync.platforms.meicheng  # noqa: F401
    import apps.cloud_platform.sync.platforms.tencent  # noqa: F401
    import apps.cloud_platform.sync.platforms.vsphere  # noqa: F401

    _platforms_loaded = True


# 引擎（会被 views.py 直接导入）
from apps.cloud_platform.sync.engine import SyncEngine  # noqa: E402

# 注册表 API
from apps.cloud_platform.sync.registry import (  # noqa: E402
    get_all_syncers,
    get_syncer,
    get_syncer_by_platform,
)

# 数据协议
from apps.cloud_platform.sync.schemas import (  # noqa: E402
    BalanceSyncData,
    DnsRecordSyncData,
    DomainSyncData,
    ServerSyncData,
    SyncResult,
)

# Agent 导出
from apps.cloud_platform.sync.agents import (  # noqa: E402
    BalanceSyncAgent,
    DnsRecordSyncAgent,
    DomainSyncAgent,
    ServerSyncAgent,
    SyncAgent,
    SyncAgentResult,
)

# Serializer 导出
from apps.cloud_platform.sync.serializers import (  # noqa: E402
    BalanceSyncSerializer,
    CloudServerSyncSerializer,
    CompanySyncSerializer,
    DnsRecordSyncSerializer,
    DomainSyncSerializer,
)

# Resolver 导出
from apps.cloud_platform.sync.resolvers import (  # noqa: E402
    DNSResolver,
    OSResolver,
    RegionResolver,
    StatusResolver,
)

# 异常导出
from apps.cloud_platform.sync.exceptions import (  # noqa: E402
    AgentExecutionError,
    ApiRequestError,
    CredentialInvalidError,
    CredentialNotFoundError,
    DataValidationError,
    DataWriteError,
    PlatformNotSupportedError,
    SerializerError,
    SyncError,
)

__all__ = [
    # 引擎与注册表
    'SyncEngine',
    'get_syncer',
    'get_syncer_by_platform',
    'get_all_syncers',
    # 数据协议
    'ServerSyncData',
    'DomainSyncData',
    'DnsRecordSyncData',
    'BalanceSyncData',
    'SyncResult',
    # Agent
    'SyncAgent',
    'SyncAgentResult',
    'ServerSyncAgent',
    'DomainSyncAgent',
    'DnsRecordSyncAgent',
    'BalanceSyncAgent',
    # Serializer
    'CloudServerSyncSerializer',
    'DomainSyncSerializer',
    'DnsRecordSyncSerializer',
    'BalanceSyncSerializer',
    'CompanySyncSerializer',
    # Resolver
    'StatusResolver',
    'OSResolver',
    'DNSResolver',
    'RegionResolver',
    # 异常
    'SyncError',
    'CredentialNotFoundError',
    'CredentialInvalidError',
    'ApiRequestError',
    'DataValidationError',
    'DataWriteError',
    'PlatformNotSupportedError',
    'AgentExecutionError',
    'SerializerError',
]
