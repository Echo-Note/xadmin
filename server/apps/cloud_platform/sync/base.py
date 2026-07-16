"""云平台资源同步抽象基类 — 纯数据拉取接口。

此基类仅负责：
1. 凭据管理（从数据库读取解密后的凭据）
2. 区域解析（从 CloudPlatform.region 解析区域列表）
3. 定义 _fetch_*() 抽象方法供子类实现

数据库写入操作已完全移除，由 Serializer 层和 Agent 层负责。
子类只需实现具体平台的 API 调用逻辑，返回 Pydantic 数据模型。
"""

from __future__ import annotations

import json
import logging
from abc import ABC

from apps.cloud_platform.sync.resolvers.region_resolver import RegionResolver

logger = logging.getLogger(__name__)


class BaseCloudSyncer(ABC):  # noqa: B024
    """云平台资源同步抽象基类。

    子类需：
    1. 设置 PLATFORM_TYPE / PLATFORM_NAMES / SUPPORTED_RESOURCES 类属性
    2. 实现 _fetch_*() 方法，返回 Pydantic 数据模型列表
    3. 使用 @register_syncer 装饰器注册

    禁止在子类中进行数据库写入操作。
    """

    PLATFORM_TYPE: str = ''
    PLATFORM_NAMES: list[str] = []
    SUPPORTED_RESOURCES: set[str] = set()

    def __init__(self, cloud_platform) -> None:  # noqa: ANN001
        """初始化同步器。

        Args:
            cloud_platform: CloudPlatform 模型实例。
        """
        self.cloud_platform = cloud_platform
        self._regions_cache: list[str] | None = None

    # ------------------------------------------------------------------
    # 凭据属性 — 从数据库读取（只读）
    # ------------------------------------------------------------------

    @property
    def credentials(self) -> dict:
        """获取当前平台的有效凭据信息。

        EncryptedTextField 字段在读取时自动解密，因此可以直接取值。
        返回包含 access_key/access_secret/username/password/api_token/email/extra_data 的字典。

        Returns:
            凭据字典，无有效凭据时返回空字典。
        """
        from apps.cloud_platform.models import Credential

        cred = Credential.objects.filter(
            platform=self.cloud_platform,
            is_active=True,
        ).first()
        if cred is None:
            return {}
        return {
            'access_key': cred.access_key,
            'access_secret': cred.access_secret,
            'username': cred.username,
            'password': cred.password,
            'api_token': cred.api_token,
            'email': cred.email,
            'extra_data': cred.extra_data or {},
        }

    # ------------------------------------------------------------------
    # 区域解析
    # ------------------------------------------------------------------

    @property
    def regions(self) -> list[str]:
        """获取解析后的区域列表（带缓存）。

        从 cloud_platform.region 字段解析，支持 JSON/逗号/分号/空格分隔。

        Returns:
            区域标识字符串列表。
        """
        if self._regions_cache is None:
            self._regions_cache = RegionResolver.parse(
                self.cloud_platform.region,
                default_regions=RegionResolver.get_default_for_platform(self.PLATFORM_TYPE),
            )
        return self._regions_cache

    # ------------------------------------------------------------------
    # 数据拉取方法 — 子类按 SUPPORTED_RESOURCES 选择性实现
    # ------------------------------------------------------------------
    # 未实现的资源类型会被 Agent 静默跳过，无需在子类中显式实现全部方法。

    def _fetch_servers(self) -> list:
        """获取云服务器列表，子类按需覆盖。

        Returns:
            ServerSyncData 对象列表。

        Raises:
            NotImplementedError: 平台不支持服务器同步。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持服务器同步')

    def _fetch_domains(self) -> list:
        """获取域名列表，子类按需覆盖。

        Returns:
            DomainSyncData 对象列表。

        Raises:
            NotImplementedError: 平台不支持域名同步。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持域名同步')

    def _fetch_dns_records(self) -> list:
        """获取 DNS 解析记录列表，子类按需覆盖。

        Returns:
            DnsRecordSyncData 对象列表。

        Raises:
            NotImplementedError: 平台不支持 DNS 记录同步。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持 DNS 记录同步')

    def _fetch_balance(self):  # noqa: ANN202
        """获取账户余额，子类按需覆盖。

        Returns:
            BalanceSyncData 对象，不支持则返回 None。

        Raises:
            NotImplementedError: 平台不支持余额同步。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持余额同步')
