"""企业主体同步序列化器 — 封装 Company 模型的查询、创建和匹配逻辑。

支持按统一社会信用代码、公司名称精确/模糊匹配，
自动创建缺失的公司主体记录。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from apps.company.models import Company
    from apps.cloud_platform.sync.schemas import DomainSyncData, SyncResult

logger = logging.getLogger(__name__)


class CompanySyncSerializer:
    """企业主体同步序列化器。

    提供 Company 查找或自动创建的幂等方法，
    所有 Company 相关的数据库操作均通过此类完成。
    每个 Agent 持有独立的实例，确保写入权限独立。
    """

    def __init__(self) -> None:
        """初始化 Company 序列化器。"""
        pass

    def find_or_create(
        self,
        company_name: str | None = None,
        credit_code: str | None = None,
        legal_person: str | None = None,
        address: str | None = None,
        result: 'SyncResult | None' = None,
    ) -> 'Company | None':
        """根据实体信息查找或自动创建 Company 主体（幂等）。

        匹配优先级：
        1. 统一社会信用代码精确匹配
        2. 公司名称精确匹配（忽略大小写）
        3. 自动创建新记录

        Args:
            company_name: 企业名称。
            credit_code: 统一社会信用代码。
            legal_person: 法定代表人。
            address: 注册地址。
            result: SyncResult 对象，用于累加 companies_created 计数。

        Returns:
            Company 实例，创建失败时返回 None。
        """
        from apps.company.models import Company

        name = (company_name or '').strip()
        code = (credit_code or '').strip()

        if not name and not code:
            return None

        company = self._match_by_credit_code(code)
        if company:
            return company

        company = self._match_by_name(name)
        if company:
            return company

        company = self._create_company(
            name=name,
            credit_code=code,
            legal_person=legal_person,
            address=address,
        )
        if company and result:
            result.companies_created += 1
        return company

    def find_or_create_from_domain(
        self,
        data: 'DomainSyncData',
        result: 'SyncResult',
    ) -> 'Company | None':
        """从域名同步数据提取实体信息并查找/创建 Company。

        处理个人主体场景：company_type='个人' 时，
        若 company_name 为空，使用联系人姓名作为公司名称。

        Args:
            data: 域名同步数据。
            result: 同步结果对象。

        Returns:
            Company 实例或 None。
        """
        company_name = data.company_name
        credit_code = data.credit_code
        legal_person = data.legal_person or None
        address = data.address or None

        # 个人主体：联系人姓名作为公司名称
        if not company_name and data.contact_person:
            company_name = data.contact_person
            logger.debug(
                '个人主体 [%s] 使用联系人姓名作为公司名称: %s',
                data.name,
                data.contact_person,
            )

        if not any([company_name, credit_code, data.contact_person]):
            return None

        return self.find_or_create(
            company_name=company_name,
            credit_code=credit_code,
            legal_person=legal_person,
            address=address,
            result=result,
        )

    # ------------------------------------------------------------------
    # 私有方法 — 数据库交互
    # ------------------------------------------------------------------

    @staticmethod
    def _match_by_credit_code(credit_code: str) -> 'Company | None':
        """按统一社会信用代码精确匹配公司。

        Args:
            credit_code: 统一社会信用代码（18位）。

        Returns:
            匹配的 Company 实例或 None。
        """
        from apps.company.models import Company

        if not credit_code:
            return None
        company = Company.objects.filter(unified_social_credit_code=credit_code).first()
        if company:
            logger.debug('按信用代码匹配到公司主体: %s → %s', credit_code, company.name)
        return company

    @staticmethod
    def _match_by_name(name: str) -> 'Company | None':
        """按公司名称精确匹配（忽略大小写）。

        Args:
            name: 公司名称。

        Returns:
            匹配的 Company 实例或 None。
        """
        from apps.company.models import Company

        if not name:
            return None
        company = Company.objects.filter(name__iexact=name).first()
        if company:
            logger.debug('按名称匹配到公司主体: %s', name)
        return company

    @staticmethod
    def _create_company(
        name: str,
        credit_code: str = '',
        legal_person: str | None = None,
        address: str | None = None,
    ) -> 'Company | None':
        """在事务中创建新的公司主体记录。

        Args:
            name: 公司名称（截断至 128 字符）。
            credit_code: 统一社会信用代码（截断至 18 字符）。
            legal_person: 法定代表人（截断至 64 字符）。
            address: 注册地址（截断至 256 字符）。

        Returns:
            新创建的 Company 实例，失败返回 None。
        """
        from apps.company.models import Company

        if not name:
            return None
        try:
            with transaction.atomic():
                company = Company.objects.create(
                    name=name[:128],
                    unified_social_credit_code=credit_code[:18] if credit_code else None,
                    legal_representative=(legal_person or '')[:64] or None,
                    registered_address=(address or '')[:256] or None,
                    is_active=True,
                )
            logger.info(
                '自动创建公司主体: %s (信用代码: %s)',
                name,
                credit_code or '无',
            )
            return company
        except Exception:
            logger.exception('创建公司主体失败: %s', name)
            return None
