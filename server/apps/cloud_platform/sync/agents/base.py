"""同步 Agent 抽象基类 — 定义 Agent 的统一接口。

每个 Agent 子类必须实现 execute() 方法，所有 Agent
均通过 Serializer 层操作数据库，确保写入权限独立且可控。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apps.cloud_platform.models import CloudPlatform, SyncAgentLog, SyncRecord
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class SyncAgentResult(BaseModel):
    """Agent 执行结果 — 包含同步统计和 AgentLog 记录所需的元数据。"""

    resource_type: str = Field(default='', description='资源类型')
    agent_name: str = Field(default='', description='Agent 名称')
    created: int = Field(default=0, ge=0, description='新建数量')
    updated: int = Field(default=0, ge=0, description='更新数量')
    terminated: int = Field(default=0, ge=0, description='终止数量')
    companies_created: int = Field(default=0, ge=0, description='自动创建企业主体数量')
    errors: list[dict] = Field(default_factory=list, description='错误列表')
    started_at: datetime | None = Field(default=None, description='Agent 开始执行时间')
    finished_at: datetime | None = Field(default=None, description='Agent 结束执行时间')
    extra_data: dict = Field(default_factory=dict, description='额外数据（写入 AgentLog.extra_data）')

    @property
    def total_changes(self) -> int:
        """所有变更总数。"""
        return self.created + self.updated + self.terminated

    @property
    def has_errors(self) -> bool:
        """是否有错误。"""
        return len(self.errors) > 0

    @property
    def error_count(self) -> int:
        """错误数量。"""
        return len(self.errors)


class SyncAgent(ABC):
    """同步 Agent 抽象基类。

    每个 Agent 负责一种资源类型的同步，拥有独立的 Serializer 实例。
    所有数据库写入通过 Serializer 层完成，业务逻辑中严禁直接使用 ORM。

    子类必须：
    - 设置 resource_type 类属性
    - 实现 execute() 方法
    """

    resource_type: str = ''

    def __init__(self, platform: CloudPlatform, platform_type: str) -> None:
        """初始化 Agent。

        Args:
            platform: CloudPlatform 模型实例。
            platform_type: 平台类型标识。
        """
        self.platform = platform
        self.platform_type = platform_type

    @abstractmethod
    def execute(self, syncer: BaseCloudSyncer) -> SyncAgentResult:
        """执行同步任务。

        子类实现具体同步逻辑：
        1. 调用 syncer._fetch_*() 获取 Pydantic 数据
        2. 通过 Serializer 层 upsert 数据到数据库
        3. 返回 SyncAgentResult

        Args:
            syncer: 平台同步器实例。

        Returns:
            Agent 执行结果。
        """
        ...

    def write_agent_log(self, sync_record: SyncRecord, result: SyncAgentResult) -> SyncAgentLog:
        """将 Agent 执行结果写入 SyncAgentLog 记录。

        Args:
            sync_record: 所属同步记录。
            result: Agent 执行结果。

        Returns:
            创建的 SyncAgentLog 实例。
        """
        from apps.cloud_platform.choices import AgentStatusChoices
        from apps.cloud_platform.models import SyncAgentLog

        agent_name = f'{self.platform_type}-{self.resource_type}'

        # 判断 Agent 整体状态
        if result.has_errors and result.total_changes == 0:
            agent_status = AgentStatusChoices.FAILED
        else:
            agent_status = AgentStatusChoices.SUCCESS

        # 将 companies_created 和 extra_data 写入 extra_data 以便追溯
        agent_extra = dict(result.extra_data)  # 复制 Agent 返回的额外数据
        if result.companies_created > 0:
            agent_extra['companies_created'] = result.companies_created

        agent_log = SyncAgentLog.objects.create(
            sync_record=sync_record,
            agent_name=agent_name,
            resource_type=self.resource_type,
            status=agent_status,
            started_at=result.started_at,
            finished_at=result.finished_at,
            created_count=result.created,
            updated_count=result.updated,
            terminated_count=result.terminated,
            error_count=result.error_count,
            error_detail=result.errors,
            extra_data=agent_extra,
        )

        logger.info(
            'Agent [%s] 完成: 新建=%d 更新=%d 错误=%d 状态=%s',
            agent_name,
            result.created,
            result.updated,
            result.error_count,
            agent_status,
        )
        return agent_log
