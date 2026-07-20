"""域名同步序列化器 — 封装 Domain 模型的数据库操作。

提供幂等的 upsert 方法，按 domain_name 唯一匹配。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.cloud_platform.models import CloudPlatform
    from apps.cloud_platform.sync.schemas import DomainSyncData, SyncResult
    from apps.company.models import Company
    from apps.domain.models import Domain

logger = logging.getLogger(__name__)


class DomainSyncSerializer:
    """域名同步序列化器。

    封装 Domain 模型的查询、创建和更新逻辑。
    每个 Agent 持有独立实例，确保写入权限独立。
    """

    def __init__(self, platform: CloudPlatform) -> None:
        """初始化。

        Args:
            platform: 当前同步的云平台实例。
        """
        self.platform = platform

    def upsert(
        self,
        data: DomainSyncData,
        result: SyncResult,
        company: Company | None = None,
    ) -> None:
        """新增或更新域名记录（幂等），按 domain_name 唯一匹配。

        Args:
            data: 域名同步数据（Pydantic 模型）。
            result: 同步结果对象。
            company: 关联的企业主体实例（可选）。
        """
        from apps.domain.models import Domain
        from apps.domain.serializers import DomainSerializer

        serializer_data = self._build_serializer_data(data, company)

        domain = Domain.objects.filter(domain_name=data.name).first()
        if domain:
            s = DomainSerializer(domain, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
            logger.debug('更新域名: %s (company: %s)', data.name, company)
        else:
            serializer_data['domain_name'] = data.name
            s = DomainSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            s.save()
            result.created += 1
            logger.debug('新增域名: %s (company: %s)', data.name, company)

    def bulk_upsert(self, data_list: list[DomainSyncData], result: SyncResult) -> None:
        """批量 upsert 域名记录。

        Args:
            data_list: 域名同步数据列表。
            result: 同步结果对象。
        """
        for data in data_list:
            try:
                self.upsert(data, result)
            except Exception:
                logger.exception('同步域名失败: %s', data.name)
                result.add_error(data.name, '域名同步异常')

    def find_by_name(self, domain_name: str) -> Domain | None:
        """按域名名称查找已有记录。

        Args:
            domain_name: 域名。

        Returns:
            Domain 实例或 None。
        """
        from apps.domain.models import Domain

        return Domain.objects.filter(domain_name=domain_name).first()

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _build_serializer_data(self, data: DomainSyncData, company: Company | None) -> dict:
        """将 Pydantic 同步数据转换为 DRF Serializer 所需字典。

        Args:
            data: 域名同步数据。
            company: 关联的企业主体。

        Returns:
            DRF Serializer 可接受的 data 字典。
        """
        serializer_data: dict = {
            'platform': str(self.platform.pk),
            'is_active': True,
        }

        if company:
            serializer_data['company'] = str(company.pk)

        # 仅设置非空值，避免空数据覆盖已有信息
        if data.registrar_name:
            serializer_data['registrar'] = data.registrar_name
        if data.register_date:
            serializer_data['registration_time'] = data.register_date
        if data.expire_date:
            serializer_data['expire_time'] = data.expire_date
        if data.dns_provider:
            serializer_data['dns_server'] = data.dns_provider
        if data.owner_name:
            serializer_data['owner_name'] = data.owner_name

        # 状态通过解析器清洗，确保值在 DomainStatusChoices 枚举范围内
        if data.status:
            from apps.cloud_platform.sync.resolvers.status_resolver import StatusResolver

            cleaned_status = StatusResolver.resolve_domain_status(data.status)
            serializer_data['status'] = cleaned_status

        return serializer_data
