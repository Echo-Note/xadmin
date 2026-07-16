"""DNS 解析记录同步 Agent — 负责 DnsRecord 同步。

持有独立的 DnsRecordSyncSerializer 实例，确保写入权限独立。
依赖 Domain 表中已有的域名记录（需在 DomainSyncAgent 之后执行）。
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.serializers.dns_record import DnsRecordSyncSerializer

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class DnsRecordSyncAgent(SyncAgent):
    """DNS 解析记录同步 Agent。

    负责从云平台拉取 DNS 解析记录，
    通过 DnsRecordSyncSerializer 写入数据库。
    DNS 记录依赖 Domain 记录已存在（需先执行 DomainSyncAgent）。
    """

    resource_type = 'dns_record'

    def execute(self, syncer: 'BaseCloudSyncer') -> SyncAgentResult:
        """执行 DNS 解析记录同步。

        流程：
        1. 调用 syncer._fetch_dns_records() 获取记录列表
        2. 通过 DnsRecordSyncSerializer 逐条 upsert
        3. 汇总统计结果

        Args:
            syncer: 平台同步器实例。

        Returns:
            Agent 执行结果。
        """
        result = SyncAgentResult(
            resource_type=self.resource_type,
            agent_name=f'{self.platform_type}-{self.resource_type}',
            started_at=datetime.now(UTC),
        )

        serializer = DnsRecordSyncSerializer(self.platform_type)

        try:
            records = syncer._fetch_dns_records()
        except NotImplementedError:
            logger.info('DNS 记录同步未实现 [%s]', self.platform_type)
            result.finished_at = datetime.now(UTC)
            return result
        except Exception as e:
            logger.exception('DNS 记录数据拉取失败 [%s]', self.platform_type)
            result.errors.append({'item': 'dns_record', 'error': str(e)})
            result.finished_at = datetime.now(UTC)
            return result

        for rec in records:
            try:
                serializer.upsert(rec, result)
            except Exception:
                logger.exception(
                    '同步DNS记录失败: %s.%s',
                    rec.domain_name,
                    rec.host_record,
                )
                result.errors.append({
                    'item': f'{rec.domain_name}.{rec.host_record}',
                    'error': 'DNS记录同步异常',
                })

        result.finished_at = datetime.now(UTC)
        logger.info(
            'DNS Agent [%s] 完成: 新建=%d 更新=%d 错误=%d',
            self.platform_type,
            result.created,
            result.updated,
            len(result.errors),
        )
        return result
