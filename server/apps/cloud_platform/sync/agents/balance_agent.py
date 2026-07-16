"""账户余额同步 Agent — 负责 CloudPlatform 余额和 AccountBalance 快照同步。

持有独立的 BalanceSyncSerializer 实例，确保写入权限独立。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.serializers.balance import BalanceSyncSerializer

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class BalanceSyncAgent(SyncAgent):
    """账户余额同步 Agent。

    负责从云平台拉取账户余额数据，
    通过 BalanceSyncSerializer 更新 CloudPlatform 余额和 AccountBalance 每日快照。
    """

    resource_type = 'balance'

    def execute(self, syncer: BaseCloudSyncer) -> SyncAgentResult:
        """执行账户余额同步。

        流程：
        1. 调用 syncer._fetch_balance() 获取余额数据
        2. 通过 BalanceSyncSerializer 保存余额
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

        serializer = BalanceSyncSerializer(self.platform)

        try:
            balance = syncer._fetch_balance()
        except NotImplementedError:
            logger.info('账户余额同步未实现 [%s]', self.platform_type)
            result.finished_at = datetime.now(UTC)
            return result
        except Exception as e:
            logger.exception('账户余额数据拉取失败 [%s]', self.platform_type)
            result.errors.append({'item': 'balance', 'error': str(e)})
            result.finished_at = datetime.now(UTC)
            return result

        if balance is None:
            result.finished_at = datetime.now(UTC)
            return result

        try:
            serializer.save(balance)
            result.updated += 1
        except Exception:
            logger.exception('保存账户余额失败 [%s]', self.platform_type)
            result.errors.append({'item': 'balance', 'error': '账户余额保存异常'})

        result.finished_at = datetime.now(UTC)
        logger.info(
            'Balance Agent [%s] 完成: 更新=%d 错误=%d',
            self.platform_type,
            result.updated,
            len(result.errors),
        )
        return result
