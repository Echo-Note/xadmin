"""同步 Agent 模块 — 每个 Agent 独立负责一种资源类型的同步。

所有 Agent 均持有独立的 Serializer 实例，**强制具备数据库写入权限**，
不存在 Agent 无法写入数据库的情况。

Agent 设计原则：
- 单一职责：每个 Agent 只负责一种资源类型
- 独立写入：每个 Agent 拥有自己的 Serializer 实例
- 并行执行：Agent 间互不依赖，可安全并行
- 错误隔离：单个 Agent 失败不影响其他 Agent
"""

from apps.cloud_platform.sync.agents.balance_agent import BalanceSyncAgent
from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.agents.dns_agent import DnsRecordSyncAgent
from apps.cloud_platform.sync.agents.domain_agent import DomainSyncAgent
from apps.cloud_platform.sync.agents.domain_post_agent import DomainPostSyncAgent
from apps.cloud_platform.sync.agents.server_agent import ServerSyncAgent
from apps.cloud_platform.sync.agents.vsphere_server_agent import VsphereServerSyncAgent

__all__ = [
    'SyncAgent',
    'SyncAgentResult',
    'ServerSyncAgent',
    'DomainSyncAgent',
    'DomainPostSyncAgent',
    'DnsRecordSyncAgent',
    'BalanceSyncAgent',
    'VsphereServerSyncAgent',
]
