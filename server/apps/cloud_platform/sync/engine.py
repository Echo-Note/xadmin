"""同步引擎 — 同步器注册与调度。

通过 @register_syncer 装饰器注册各平台同步器，引擎负责按平台类型分派同步任务。
"""

import logging
from datetime import UTC

from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)

# 全局同步器注册表：{platform_type: SyncerClass}
_syncer_registry: dict[str, type[BaseCloudSyncer]] = {}


def register_syncer(cls: type[BaseCloudSyncer]) -> type[BaseCloudSyncer]:
    """装饰器：将同步器类注册到全局注册表。

    Usage:
        @register_syncer
        class TencentCloudSyncer(BaseCloudSyncer):
            PLATFORM_TYPE = "tencent"
            ...

    Args:
        cls: 同步器子类。

    Returns:
        原类，不做修改。
    """
    if cls.PLATFORM_TYPE:
        _syncer_registry[cls.PLATFORM_TYPE] = cls
        logger.debug('已注册同步器: %s -> %s', cls.PLATFORM_TYPE, cls.__name__)
    return cls


def get_syncer(platform_type: str) -> type[BaseCloudSyncer] | None:
    """根据平台类型获取已注册的同步器类。

    Args:
        platform_type: 平台类型标识（如 'tencent'/'aliyun'）。

    Returns:
        同步器类，未注册时返回 None。
    """
    return _syncer_registry.get(platform_type)


def get_all_syncers() -> dict[str, type[BaseCloudSyncer]]:
    """获取所有已注册的同步器。

    Returns:
        {platform_type: SyncerClass} 字典。
    """
    return dict(_syncer_registry)


def get_syncer_by_platform(cloud_platform) -> BaseCloudSyncer | None:  # noqa: ANN001
    """根据 CloudPlatform 实例获取对应的同步器实例。

    匹配优先级：
    1. platform_type 精确匹配
    2. name 精确匹配（大小写不敏感）
    3. name 子串包含匹配

    Args:
        cloud_platform: CloudPlatform 模型实例。

    Returns:
        同步器实例，未匹配到则返回 None。
    """
    platform_type = cloud_platform.platform_type
    platform_name = cloud_platform.name

    # 1. platform_type 精确匹配
    if platform_type and platform_type in _syncer_registry:
        return _syncer_registry[platform_type](cloud_platform)

    # 2. name 精确匹配
    name_lower = platform_name.lower().strip()
    for syncer_cls in _syncer_registry.values():
        for alias in getattr(syncer_cls, 'PLATFORM_NAMES', []):
            if alias.lower() == name_lower:
                return syncer_cls(cloud_platform)

    # 3. name 子串包含匹配
    for key, syncer_cls in _syncer_registry.items():
        if key in name_lower or name_lower in key:
            return syncer_cls(cloud_platform)

    return None


class SyncEngine:
    """同步引擎 — 驱动同步流程并记录 SyncRecord 和 SyncAgentLog。"""

    def run(self, cloud_platform, sync_type: str = 'manual', resources: list[str] | None = None):  # noqa: ANN001, ANN201
        """执行同步流程。

        Args:
            cloud_platform: CloudPlatform 模型实例。
            sync_type: 触发类型 (manual/scheduled/webhook)。
            resources: 需同步的资源类型，None=全部。

        Returns:
            SyncRecord 实例。
        """
        logger = logging.getLogger(__name__)
        from datetime import datetime

        from apps.cloud_platform.choices import AgentStatusChoices, SyncStatusChoices
        from apps.cloud_platform.models import SyncAgentLog, SyncRecord

        sync_record = SyncRecord.objects.create(
            platform=cloud_platform,
            sync_type=sync_type,
            status=SyncStatusChoices.RUNNING,
            resources=resources or [],
            started_at=datetime.now(UTC),
        )

        syncer = get_syncer_by_platform(cloud_platform)
        if syncer is None:
            sync_record.status = SyncStatusChoices.FAILED
            sync_record.finished_at = datetime.now(UTC)
            sync_record.error_detail = [
                {'item': cloud_platform.name, 'error': f'未找到平台类型 [{cloud_platform.platform_type}] 的同步器'}
            ]
            sync_record.total_errors = 1
            sync_record.save()
            return sync_record

        all_results: dict = {}
        try:
            all_results = syncer.sync_all(resources)
        except Exception as e:
            logger.exception('同步 [%s] 时发生未预期错误', cloud_platform.name)
            sync_record.status = SyncStatusChoices.FAILED
            sync_record.error_detail = [{'item': cloud_platform.name, 'error': str(e)}]
            sync_record.total_errors = 1
            sync_record.finished_at = datetime.now(UTC)
            sync_record.save()
            return sync_record

        # 汇总并写 AgentLog
        total_created = total_updated = total_terminated = 0
        total_companies_created = 0
        all_errors = []

        for resource_type, result in all_results.items():
            total_created += result.created
            total_updated += result.updated
            total_terminated += result.terminated
            total_companies_created += result.companies_created
            all_errors.extend(result.errors)

            agent_name = f'{syncer.PLATFORM_TYPE}-{resource_type}'
            agent_status = (
                AgentStatusChoices.FAILED
                if result.has_errors and result.total_changes == 0
                else AgentStatusChoices.SUCCESS
            )
            # 将 companies_created 写入 extra_data 以便追溯
            agent_extra = {}
            if result.companies_created > 0:
                agent_extra['companies_created'] = result.companies_created

            SyncAgentLog.objects.create(
                sync_record=sync_record,
                agent_name=agent_name,
                resource_type=resource_type,
                status=agent_status,
                started_at=sync_record.started_at,
                finished_at=datetime.now(UTC),
                created_count=result.created,
                updated_count=result.updated,
                terminated_count=result.terminated,
                error_count=len(result.errors),
                error_detail=result.errors,
                extra_data=agent_extra,
            )

        if len(all_errors) == 0:
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

        if total_companies_created > 0:
            logger.info(
                '同步 [%s] 完成: 新建 %d, 更新 %d, 终止 %d, 错误 %d, 自动创建企业主体 %d',
                cloud_platform.name,
                total_created,
                total_updated,
                total_terminated,
                len(all_errors),
                total_companies_created,
            )
        else:
            logger.info(
                '同步 [%s] 完成: 新建 %d, 更新 %d, 终止 %d, 错误 %d',
                cloud_platform.name,
                total_created,
                total_updated,
                total_terminated,
                len(all_errors),
            )

        return sync_record
