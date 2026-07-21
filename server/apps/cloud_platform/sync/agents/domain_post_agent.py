"""域名同步后处理 Agent — SSL 证书检测 + 备案信息联动 + ICP 预检测异步派发。

在域名同步和 DNS 记录同步完成后执行（Phase 3）：
1. 遍历当前平台的所有活跃域名
2. 有 www DNS 解析记录的域名：创建 Filing 备案记录 + 检测 SSL 证书
3. 无 www DNS 解析记录的域名：删除已有的 Filing 备案记录
4. 异步派发 ICP 预检测到 Celery 队列（不阻塞同步流程）

该 Agent 不从云平台拉取数据，而是基于已同步的 Domain + DnsRecord
进行本地后处理，因此不需要 syncer 支持。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class DomainPostSyncAgent(SyncAgent):
    """域名同步后处理 Agent。

    在域名 + DNS 记录同步完成后执行 SSL 证书检测和 Filing 备案信息联动。
    Filing 备案记录仅在域名存在 www DNS 解析记录时创建。
    ICP 预检测通过 Celery 异步派发，不阻塞同步流程。
    """

    resource_type = 'domain_post'

    def execute(self, syncer: BaseCloudSyncer) -> SyncAgentResult:
        """执行域名后处理：www 记录检测 → SSL 检测 → Filing 联动 → ICP 预检测派发。

        Args:
            syncer: 平台同步器实例（本 Agent 不使用 syncer 拉取数据，
                    仅基于已同步的 Domain + DnsRecord 进行本地处理）。

        Returns:
            Agent 执行结果（precheck 派发信息存储在 result.extra_data 中）。
        """
        from apps.domain.post_sync import process_domains_post_sync

        result = SyncAgentResult(
            resource_type=self.resource_type,
            agent_name=f'{self.platform_type}-{self.resource_type}',
            started_at=datetime.now(UTC),
        )

        stats: dict = {}
        try:
            stats = process_domains_post_sync(self.platform)

            # 将后处理统计映射到 Agent 结果
            result.created = stats.get('filings_created', 0) + stats.get('ssl_certificates_created', 0)
            result.updated = stats.get('ssl_enabled', 0)
            result.terminated = stats.get('filings_removed', 0)
            result.errors = stats.get('errors', [])

            # 预检测派发信息存入 result.extra_data（write_agent_log 会写入 AgentLog）
            if stats.get('precheck_total', 0) > 0:
                result.extra_data['precheck'] = {
                    'dispatched': stats.get('precheck_dispatched', False),
                    'task_id': stats.get('precheck_task_id'),
                    'total': stats.get('precheck_total', 0),
                }
        except Exception as e:
            logger.exception('域名后处理失败 [%s]', self.platform.name)
            result.errors.append({'item': 'domain_post', 'error': str(e)})

        result.finished_at = datetime.now(UTC)
        logger.info(
            'DomainPost Agent [%s] 完成: Filing新建=%d 删除=%d SSL可用=%d 证书新建=%d ICP预检测派发=%s 错误=%d',
            self.platform_type,
            stats.get('filings_created', 0),
            stats.get('filings_removed', 0),
            stats.get('ssl_enabled', 0),
            stats.get('ssl_certificates_created', 0),
            '是' if stats.get('precheck_dispatched') else '否',
            len(result.errors),
        )
        return result
