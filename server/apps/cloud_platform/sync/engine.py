"""同步引擎 — 多 Agent 并行调度与结果聚合。

核心职责：
1. 接收同步请求，创建 SyncRecord
2. 按平台类型查找同步器 + 匹配资源类型 → 创建 Agent 列表
3. 使用线程池并行执行各 Agent
4. 聚合 Agent 结果，写入 SyncAgentLog
5. 更新 SyncRecord 最终状态

所有 Agent 均通过 Serializer 层操作数据库，确保写入权限独立。
Agent 间按依赖关系分组（domain 先于 dns_record），组内并行。
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.balance_agent import BalanceSyncAgent
from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.agents.dns_agent import DnsRecordSyncAgent
from apps.cloud_platform.sync.agents.domain_agent import DomainSyncAgent
from apps.cloud_platform.sync.agents.server_agent import ServerSyncAgent
from apps.cloud_platform.sync.agents.vsphere_server_agent import VsphereServerSyncAgent
from apps.cloud_platform.sync.registry import get_syncer_by_platform

if TYPE_CHECKING:
    from apps.cloud_platform.models import CloudPlatform, SyncRecord

logger = logging.getLogger(__name__)


class SyncEngine:
    """同步引擎 — 驱动多 Agent 并行同步流程。

    Usage:
        engine = SyncEngine()
        sync_record = engine.run(cloud_platform, sync_type='manual', resources=['server', 'domain'])
    """

    # Agent 阶段分组（保证依赖顺序：domain 在 dns_record 之前）
    PHASE_GROUPS: list[list[str]] = [
        ['server', 'domain', 'balance'],  # Phase 1: 独立并行
        ['dns_record'],  # Phase 2: 依赖 Domain 已存在
    ]

    # 资源类型 → Agent 类的映射
    AGENT_FACTORY: dict[str, type[SyncAgent]] = {
        'server': ServerSyncAgent,
        'domain': DomainSyncAgent,
        'dns_record': DnsRecordSyncAgent,
        'balance': BalanceSyncAgent,
    }

    def run(
        self,
        cloud_platform: CloudPlatform,
        sync_type: str = 'manual',
        resources: list[str] | None = None,
    ) -> SyncRecord:
        """执行同步流程。

        Args:
            cloud_platform: CloudPlatform 模型实例。
            sync_type: 触发类型 (manual/scheduled/webhook)。
            resources: 需同步的资源类型列表，None=全部。

        Returns:
            SyncRecord 实例。
        """
        from apps.cloud_platform.choices import SyncStatusChoices
        from apps.cloud_platform.models import SyncRecord
        from apps.cloud_platform.sync import _ensure_platforms_loaded

        # 确保所有平台同步器已注册
        _ensure_platforms_loaded()

        # ---- Step 1: 创建 SyncRecord ----
        sync_record = SyncRecord.objects.create(
            platform=cloud_platform,
            sync_type=sync_type,
            status=SyncStatusChoices.RUNNING,
            resources=resources or [],
            started_at=datetime.now(UTC),
        )

        # ---- Step 2: 查找同步器 ----
        syncer = get_syncer_by_platform(cloud_platform)
        if syncer is None:
            return self._fail_record(
                sync_record,
                f'未找到平台类型 [{cloud_platform.platform_type}] 的同步器',
            )

        # ---- Step 3: 确定需同步的资源类型 ----
        if resources:
            target_resources = [r for r in resources if r in syncer.SUPPORTED_RESOURCES]
        else:
            target_resources = list(syncer.SUPPORTED_RESOURCES)

        if not target_resources:
            return self._fail_record(
                sync_record,
                f'平台 [{cloud_platform.name}] 不支持任何资源同步',
            )

        # ---- Step 4: 分阶段并行执行 Agent ----
        all_results: dict[str, SyncAgentResult] = {}

        try:
            for phase_group in self.PHASE_GROUPS:
                phase_resources = [r for r in phase_group if r in target_resources]
                if not phase_resources:
                    continue

                phase_results = self._execute_phase(
                    syncer=syncer,
                    platform=cloud_platform,
                    resource_types=phase_resources,
                )
                all_results.update(phase_results)
        except Exception as e:
            logger.exception('同步 [%s] 时发生未预期错误', cloud_platform.name)
            return self._fail_record(sync_record, str(e))

        # ---- Step 5: 写入 AgentLog 并汇总 SyncRecord ----
        self._finalize(sync_record, all_results, cloud_platform)

        return sync_record

    # ------------------------------------------------------------------
    # 阶段并行执行
    # ------------------------------------------------------------------

    def _execute_phase(
        self,
        syncer,  # noqa: ANN001
        platform: CloudPlatform,
        resource_types: list[str],
    ) -> dict[str, SyncAgentResult]:
        """并行执行同一阶段内的多个 Agent。

        Args:
            syncer: 平台同步器实例。
            platform: CloudPlatform 实例。
            resource_types: 本阶段需执行的资源类型列表。

        Returns:
            {resource_type: SyncAgentResult} 字典。
        """
        results: dict[str, SyncAgentResult] = {}

        if len(resource_types) == 1:
            # 单 Agent：直接在当前线程执行，减少线程开销
            rt = resource_types[0]
            agent = self._create_agent(rt, platform)
            results[rt] = agent.execute(syncer)
            return results

        # 多 Agent：线程池并行执行
        with ThreadPoolExecutor(max_workers=len(resource_types)) as executor:
            futures: dict = {}
            for rt in resource_types:
                agent = self._create_agent(rt, platform)
                future = executor.submit(agent.execute, syncer)
                futures[future] = rt

            for future in as_completed(futures):
                rt = futures[future]
                try:
                    results[rt] = future.result()
                except Exception as e:
                    logger.exception('Agent [%s] 执行异常', rt)
                    results[rt] = SyncAgentResult(
                        resource_type=rt,
                        agent_name=f'{syncer.PLATFORM_TYPE}-{rt}',
                        errors=[{'item': rt, 'error': str(e)}],
                        started_at=datetime.now(UTC),
                        finished_at=datetime.now(UTC),
                    )

        return results

    def _create_agent(self, resource_type: str, platform: CloudPlatform) -> SyncAgent:
        """根据资源类型和平台类型创建对应的 Agent 实例。

        vCenter/vSphere 平台使用 VsphereServerSyncAgent（两阶段同步：
        物理主机→LocalServer，虚拟机→LocalVM）。

        Args:
            resource_type: 资源类型标识。
            platform: CloudPlatform 实例。

        Returns:
            Agent 实例。
        """
        if platform.platform_type == 'vcenter' and resource_type == 'server':
            return VsphereServerSyncAgent(platform, platform.platform_type)

        agent_cls = self.AGENT_FACTORY.get(resource_type)
        if agent_cls is None:
            raise ValueError(f'未知的资源类型: {resource_type}')
        return agent_cls(platform, platform.platform_type)

    # ------------------------------------------------------------------
    # 结果聚合与持久化
    # ------------------------------------------------------------------

    def _finalize(
        self,
        sync_record: SyncRecord,
        all_results: dict[str, SyncAgentResult],
        platform: CloudPlatform,
    ) -> None:
        """汇总 Agent 结果，写入 SyncAgentLog，更新 SyncRecord 最终状态。

        Args:
            sync_record: 同步记录。
            all_results: 所有 Agent 执行结果。
            platform: CloudPlatform 实例。
        """
        from apps.cloud_platform.choices import SyncStatusChoices

        total_created = 0
        total_updated = 0
        total_terminated = 0
        all_errors: list[dict] = []
        total_companies_created = 0

        # 按依赖顺序写入 AgentLog
        for phase_group in self.PHASE_GROUPS:
            for rt in phase_group:
                result = all_results.get(rt)
                if result is None:
                    continue

                total_created += result.created
                total_updated += result.updated
                total_terminated += result.terminated
                total_companies_created += result.companies_created
                all_errors.extend(result.errors)

                # 创建 Agent 实例来写日志
                agent = self._create_agent(rt, platform)
                agent.write_agent_log(sync_record, result)

        # 判断整体状态
        if not all_errors:
            sync_record.status = SyncStatusChoices.SUCCESS
        elif total_created + total_updated + total_terminated > 0:
            sync_record.status = SyncStatusChoices.PARTIAL
        else:
            sync_record.status = SyncStatusChoices.FAILED

        sync_record.total_created = total_created
        sync_record.total_updated = total_updated
        sync_record.total_terminated = total_terminated
        sync_record.total_errors = len(all_errors)
        sync_record.error_detail = all_errors
        sync_record.finished_at = datetime.now(UTC)
        sync_record.save()

        self._log_summary(
            platform_name=platform.name,
            total_created=total_created,
            total_updated=total_updated,
            total_terminated=total_terminated,
            total_errors=len(all_errors),
            total_companies_created=total_companies_created,
        )

    @staticmethod
    def _fail_record(sync_record: SyncRecord, error_msg: str) -> SyncRecord:
        """将 SyncRecord 标记为失败。

        Args:
            sync_record: 同步记录。
            error_msg: 错误信息。

        Returns:
            更新后的 SyncRecord。
        """
        from apps.cloud_platform.choices import SyncStatusChoices

        sync_record.status = SyncStatusChoices.FAILED
        sync_record.finished_at = datetime.now(UTC)
        sync_record.error_detail = [{'item': sync_record.platform.name, 'error': error_msg}]
        sync_record.total_errors = 1
        sync_record.save()
        logger.error('同步 [%s] 失败: %s', sync_record.platform.name, error_msg)
        return sync_record

    @staticmethod
    def _log_summary(
        platform_name: str,
        total_created: int,
        total_updated: int,
        total_terminated: int,
        total_errors: int,
        total_companies_created: int = 0,
    ) -> None:
        """输出同步完成日志。

        Args:
            platform_name: 平台名称。
            total_created: 新建总数。
            total_updated: 更新总数。
            total_terminated: 终止总数。
            total_errors: 错误总数。
            total_companies_created: 自动创建企业主体数量。
        """
        base_msg = (
            f'同步 [{platform_name}] 完成: '
            f'新建 {total_created}, 更新 {total_updated}, '
            f'终止 {total_terminated}, 错误 {total_errors}'
        )
        if total_companies_created > 0:
            base_msg += f', 自动创建企业主体 {total_companies_created}'
        logger.info(base_msg)
