"""DNS 解析记录同步序列化器 — 封装 DnsRecord 模型的数据库操作。

提供幂等的 upsert 方法，按 domain + record_type + host + value 组合唯一匹配。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.resolvers.dns_resolver import DNSResolver

if TYPE_CHECKING:
    from apps.asset.models import Domain
    from apps.cloud_platform.sync.schemas import DnsRecordSyncData, SyncResult

logger = logging.getLogger(__name__)


class DnsRecordSyncSerializer:
    """DNS 解析记录同步序列化器。

    封装 DnsRecord 模型的查询、创建和更新逻辑。
    每个 Agent 持有独立实例，确保写入权限独立。
    """

    def __init__(self, platform_type: str = '') -> None:
        """初始化。

        Args:
            platform_type: 平台类型标识，用于 DNS 归属判断。
        """
        self.platform_type = platform_type

    def upsert(self, data: DnsRecordSyncData, result: SyncResult) -> None:
        """新增或更新 DNS 解析记录（幂等）。

        按 domain + record_type + host + value 组合唯一匹配。
        域名不在资产库或 DNS 不由当前平台托管时静默跳过。

        Args:
            data: DNS 记录同步数据（Pydantic 模型）。
            result: 同步结果对象。
        """
        from apps.asset.models import DnsRecord
        from apps.asset.serializers import DnsRecordSerializer

        domain = self._get_domain(data.domain_name)
        if not domain:
            logger.debug('域名 [%s] 不在资产库中，跳过 DNS 记录', data.domain_name)
            return

        if not self._is_platform_dns(domain):
            logger.debug('域名 [%s] DNS 不由当前平台管理，跳过', data.domain_name)
            return

        record = DnsRecord.objects.filter(
            domain=domain,
            record_type=data.record_type,
            host=data.host_record,
            value=data.record_value,
        ).first()

        serializer_data = {
            'domain': str(domain.pk),
            'record_type': data.record_type,
            'host': data.host_record,
            'value': data.record_value,
            'ttl': data.ttl or 600,
            'priority': data.priority or 0,
            'is_active': True,
        }

        if record:
            s = DnsRecordSerializer(record, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
        else:
            s = DnsRecordSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            s.save()
            result.created += 1

    def bulk_upsert(self, data_list: list[DnsRecordSyncData], result: SyncResult) -> None:
        """批量 upsert DNS 解析记录。

        Args:
            data_list: DNS 记录同步数据列表。
            result: 同步结果对象。
        """
        for data in data_list:
            try:
                self.upsert(data, result)
            except Exception:
                logger.exception(
                    '同步DNS记录失败: %s.%s',
                    data.domain_name,
                    data.host_record,
                )
                result.add_error(
                    f'{data.domain_name}.{data.host_record}',
                    'DNS记录同步异常',
                )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_domain(domain_name: str) -> Domain | None:
        """按域名名称查找 Domain 记录。

        Args:
            domain_name: 域名。

        Returns:
            Domain 实例或 None。
        """
        from apps.asset.models import Domain

        return Domain.objects.filter(domain_name=domain_name).first()

    def _is_platform_dns(self, domain: Domain) -> bool:
        """判断域名 DNS 是否由当前平台管理。

        Args:
            domain: Domain 模型实例。

        Returns:
            True 表示 DNS 由当前平台托管。
        """
        if not self.platform_type:
            return True
        return DNSResolver.is_managed_by(domain.dns_server or '', self.platform_type)
