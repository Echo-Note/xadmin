"""vSphere 服务器同步 Agent — 负责 ESXi 宿主机和虚拟机的两阶段同步。

阶段 1：同步 ESXi 物理宿主机 → LocalServer 模型
阶段 2：同步虚拟机 → LocalVM 模型（关联已同步的宿主机）
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.serializers.local_server import LocalServerSyncSerializer
from apps.cloud_platform.sync.serializers.local_vm import LocalVMSyncSerializer

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class VsphereServerSyncAgent(SyncAgent):
    """vSphere 服务器同步 Agent。

    处理 ESXi 宿主机（physical）和虚拟机（virtual）两类资产：
    - 第一阶段：同步所有 physical 类型 → LocalServer
    - 第二阶段：同步所有 virtual 类型 → LocalVM（关联 LocalServer）
    """

    resource_type = 'server'

    def execute(self, syncer: BaseCloudSyncer) -> SyncAgentResult:
        """执行 vSphere 资产两阶段同步。

        Args:
            syncer: VsphereSyncer 实例。

        Returns:
            Agent 执行结果。
        """
        result = SyncAgentResult(
            resource_type=self.resource_type,
            agent_name=f'{self.platform_type}-{self.resource_type}',
            started_at=datetime.now(UTC),
        )

        try:
            servers = syncer._fetch_servers()
        except NotImplementedError:
            logger.info('vSphere 服务器同步未实现 [%s]', self.platform_type)
            result.finished_at = datetime.now(UTC)
            return result
        except Exception as e:
            logger.exception('vSphere 数据拉取失败 [%s]', self.platform_type)
            result.errors.append({'item': 'server', 'error': str(e)})
            result.finished_at = datetime.now(UTC)
            return result

        if not servers:
            logger.info('vSphere 未拉取到任何服务器数据')
            result.finished_at = datetime.now(UTC)
            return result

        # 分类：物理宿主机 vs 虚拟机
        physical = [s for s in servers if s.server_type == 'physical']
        virtual = [s for s in servers if s.server_type == 'virtual']

        logger.info(
            'vSphere 资产分类: 物理宿主机 %d, 虚拟机 %d',
            len(physical),
            len(virtual),
        )

        # ---- Phase 1: 同步物理宿主机 → LocalServer ----
        host_serializer = LocalServerSyncSerializer(self.platform)
        for srv in physical:
            try:
                host_serializer.upsert(srv, result)
            except Exception:
                logger.exception('同步物理主机失败: %s', srv.hostname)
                result.errors.append({'item': srv.hostname, 'error': '物理主机同步异常'})

        # ---- Phase 2: 同步虚拟机 → LocalVM（关联宿主机）----
        vm_serializer = LocalVMSyncSerializer(self.platform)
        for srv in virtual:
            try:
                vm_serializer.upsert(srv, result)
            except Exception:
                logger.exception('同步虚拟机失败: %s', srv.hostname)
                result.errors.append({'item': srv.hostname, 'error': '虚拟机同步异常'})

        result.finished_at = datetime.now(UTC)
        logger.info(
            'vSphere Agent [%s] 完成: 新建=%d 更新=%d 错误=%d',
            self.platform_type,
            result.created,
            result.updated,
            len(result.errors),
        )
        return result
