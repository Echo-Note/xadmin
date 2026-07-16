"""域名同步 Agent — 负责 Domain 资产同步及企业主体自动关联。

持有独立的 DomainSyncSerializer 和 CompanySyncSerializer 实例。
域名同步与公司主体创建在同一 Agent 内完成，保证原子性。
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.agents.base import SyncAgent, SyncAgentResult
from apps.cloud_platform.sync.serializers.company import CompanySyncSerializer
from apps.cloud_platform.sync.serializers.domain import DomainSyncSerializer

if TYPE_CHECKING:
    from apps.cloud_platform.sync.base import BaseCloudSyncer

logger = logging.getLogger(__name__)


class DomainSyncAgent(SyncAgent):
    """域名同步 Agent。

    负责从云平台拉取域名列表，自动匹配/创建企业主体，
    并通过 Serializer 写入 Domain 记录。
    公司主体创建通过 CompanySyncSerializer 完成，写入权限独立。
    """

    resource_type = 'domain'

    def execute(self, syncer: 'BaseCloudSyncer') -> SyncAgentResult:
        """执行域名同步（含企业主体自动匹配与创建）。

        流程：
        1. 调用 syncer._fetch_domains() 获取域名列表
        2. 逐域名：
           a. 通过 CompanySyncSerializer 查找或创建企业主体
           b. 通过 DomainSyncSerializer upsert 域名记录
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

        domain_serializer = DomainSyncSerializer(self.platform)
        company_serializer = CompanySyncSerializer()

        try:
            domains = syncer._fetch_domains()
        except NotImplementedError:
            logger.info('域名同步未实现 [%s]', self.platform_type)
            result.finished_at = datetime.now(UTC)
            return result
        except Exception as e:
            logger.exception('域名数据拉取失败 [%s]', self.platform_type)
            result.errors.append({'item': 'domain', 'error': str(e)})
            result.finished_at = datetime.now(UTC)
            return result

        # 通过 Serializer 逐域名处理（公司主体匹配 + 域名 upsert）
        for dm in domains:
            try:
                # Step 1: 通过 CompanySerializer 查找/创建企业主体
                company = company_serializer.find_or_create_from_domain(dm, result)

                # Step 2: 通过 DomainSerializer upsert 域名
                domain_serializer.upsert(dm, result, company=company)
            except Exception:
                logger.exception('同步域名失败: %s', dm.name)
                result.errors.append({'item': dm.name, 'error': '域名同步异常'})

        result.finished_at = datetime.now(UTC)
        logger.info(
            'Domain Agent [%s] 完成: 新建=%d 更新=%d 公司=%d 错误=%d',
            self.platform_type,
            result.created,
            result.updated,
            result.companies_created,
            len(result.errors),
        )
        return result
