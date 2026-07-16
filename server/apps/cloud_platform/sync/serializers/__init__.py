"""同步专用序列化器模块 — 封装所有数据库交互。

业务逻辑层严禁直接使用 ORM 操作数据库，
所有数据写入、查询、匹配操作必须通过此模块的序列化器完成。

每个同步资源类型对应一个独立的同步序列化器，
提供幂等的 upsert 方法。
"""

from apps.cloud_platform.sync.serializers.balance import BalanceSyncSerializer
from apps.cloud_platform.sync.serializers.company import CompanySyncSerializer
from apps.cloud_platform.sync.serializers.dns_record import DnsRecordSyncSerializer
from apps.cloud_platform.sync.serializers.domain import DomainSyncSerializer
from apps.cloud_platform.sync.serializers.local_server import LocalServerSyncSerializer
from apps.cloud_platform.sync.serializers.local_vm import LocalVMSyncSerializer
from apps.cloud_platform.sync.serializers.server import CloudServerSyncSerializer

__all__ = [
    'CloudServerSyncSerializer',
    'DomainSyncSerializer',
    'DnsRecordSyncSerializer',
    'BalanceSyncSerializer',
    'CompanySyncSerializer',
    'LocalServerSyncSerializer',
    'LocalVMSyncSerializer',
]
