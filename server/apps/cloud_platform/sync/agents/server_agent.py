"""云服务器同步 Agent — 负责 CloudServer 资产同步。

持有独立的 CloudServerSyncSerializer 实例，确保写入权限独立。
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.serializers.server import CloudServerSyncSerializer

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class ServerSyncAgent(SyncAgent):
    """云服务器同步 Agent。

    负责从云平台拉取云服务器列表并通过 Serializer 写入数据库。
    """

    resource_type = 'server'

    def execute(self, syncer: 'BaseCloudSyncer') -> SyncAgentResult:
        """执行云服务器同步。

        流程：
        1. 调用 syncer._fetch_servers() 获取 Pydantic 数据
        2. 通过 CloudServerSyncSerializer 批量 upsert
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

        serializer = CloudServerSyncSerializer(self.platform)

        try:
            servers = syncer._fetch_servers()
        except NotImplementedError:
            logger.info('云服务器同步未实现 [%s]', self.platform_type)
            result.finished_at = datetime.now(UTC)
            return result
        except Exception as e:
            logger.exception('云服务器数据拉取失败 [%s]', self.platform_type)
            result.errors.append({'item': 'server', 'error': str(e)})
            result.finished_at = datetime.now(UTC)
            return result

        # 通过 Serializer 批量写入（每个 item 独立异常处理）
        for srv in servers:
            try:
                serializer.upsert(srv, result)
            except Exception:
                logger.exception('同步云服务器失败: %s', srv.hostname)
                result.errors.append({'item': srv.hostname, 'error': '服务器同步异常'})

        result.finished_at = datetime.now(UTC)
        logger.info(
            'Server Agent [%s] 完成: 新建=%d 更新=%d 错误=%d',
            self.platform_type,
            result.created,
            result.updated,
            len(result.errors),
        )
        return result
