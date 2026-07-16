"""云平台资源同步抽象基类 — 纯数据拉取接口。

此基类仅负责：
1. 凭据管理（从数据库读取解密后的凭据）
2. 区域解析（从 CloudPlatform.region 解析区域列表）
3. 定义 _fetch_*() 抽象方法供子类实现
4. 提供通用的并行区域执行和重试机制

数据库写入操作已完全移除，由 Serializer 层和 Agent 层负责。
子类只需实现具体平台的 API 调用逻辑，返回 Pydantic 数据模型。
"""

from __future__ import annotations

import logging
import time
from abc import ABC
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

from apps.cloud_platform.sync.resolvers.region_resolver import RegionResolver

logger = logging.getLogger(__name__)

T = TypeVar('T')


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

    # 并行区域拉取最大并发数（子类可覆盖）
    MAX_REGION_WORKERS: int = 5
    # 重试配置
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: float = 1.0  # 指数退避基础秒数

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

    # ------------------------------------------------------------------
    # 通用工具方法 — 并行区域执行 & 重试
    # ------------------------------------------------------------------

    def _fetch_by_regions(
        self,
        fetch_func: Callable[[str], list[T]],
        merge: bool = True,
    ) -> list[T]:
        """并行遍历所有区域执行拉取函数，合并结果。

        Args:
            fetch_func: 接收 region 参数、返回数据列表的可调用对象。
            merge: 是否合并各区域结果为单一列表。

        Returns:
            合并后的数据列表（merge=True）或 {region: list} 字典（merge=False）。
        """
        results: list[T] = []
        regions = self.regions
        if not regions:
            return results

        if len(regions) == 1:
            try:
                return fetch_func(regions[0])
            except Exception:
                logger.exception('[%s] 区域[%s] 数据拉取失败', self.PLATFORM_TYPE, regions[0])
                return results

        with ThreadPoolExecutor(max_workers=min(self.MAX_REGION_WORKERS, len(regions))) as executor:
            future_to_region = {executor.submit(fetch_func, region): region for region in regions}
            for future in as_completed(future_to_region):
                region = future_to_region[future]
                try:
                    results.extend(future.result())
                except Exception:
                    logger.exception('[%s] 区域[%s] 数据拉取失败', self.PLATFORM_TYPE, region)

        return results

    @staticmethod
    def _retry(
        func: Callable[[], T],
        max_retries: int | None = None,
        backoff: float | None = None,
        label: str = '',
    ) -> T | None:
        """带指数退避的重试执行。

        自动跳过不可重试的错误（参数校验/认证失败等）。

        Args:
            func: 无参可调用对象。
            max_retries: 最大重试次数，默认使用类属性。
            backoff: 初始退避秒数，默认使用类属性。
            label: 日志标签。

        Returns:
            函数返回值，全部失败返回 None。
        """
        last_exc = None
        retries = max_retries if max_retries is not None else BaseCloudSyncer.MAX_RETRIES
        delay = backoff if backoff is not None else BaseCloudSyncer.RETRY_BACKOFF

        for attempt in range(retries):
            try:
                return func()
            except Exception as e:
                last_exc = e
                # 不可重试的错误：参数校验类、认证类
                if BaseCloudSyncer._is_non_retryable(e):
                    logger.error(
                        '%s不可重试错误，放弃: %s',
                        f'[{label}] ' if label else '',
                        e,
                    )
                    return None
                if attempt < retries - 1:
                    wait = delay * (2**attempt)
                    logger.warning(
                        '%s重试 %d/%d，等待 %.1fs: %s',
                        f'[{label}] ' if label else '',
                        attempt + 1,
                        retries,
                        wait,
                        e,
                    )
                    time.sleep(wait)

        logger.error('%s全部 %d 次重试失败: %s', f'[{label}] ' if label else '', retries, last_exc)
        return None

    @staticmethod
    def _is_non_retryable(exception: Exception) -> bool:
        """判断异常是否为不可重试类型。

        参数校验、认证失败、权限不足等错误重试无意义。

        Args:
            exception: 捕获的异常。

        Returns:
            True 表示不应重试。
        """
        # 腾讯云 SDK 错误码
        tc_code = getattr(exception, 'code', '') or ''
        if tc_code in (
            'InvalidParameterValue',
            'InvalidParameter',
            'MissingParameter',
            'AuthFailure',
            'UnauthorizedOperation',
            'ResourceNotFound',
        ):
            return True

        # 阿里云 SDK 错误码
        ali_code = getattr(exception, 'error_code', '') or ''
        if ali_code and 'Invalid' in ali_code:
            return True

        # 华为云 SDK 错误码
        hw_code = getattr(exception, 'error_code', '') or ''
        if hw_code and 'Invalid' in hw_code:
            return True

        # HTTP 4xx 客户端错误不重试
        status = getattr(exception, 'status_code', 0) or 0
        if 400 <= status < 500:
            return True

        return False
