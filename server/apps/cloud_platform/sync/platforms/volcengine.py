"""火山引擎同步器 — 账户余额同步。

使用 volcengine SDK（volc-sdk-python），通过 QueryBalanceAcct API 查询账户余额。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

from apps.cloud_platform.sync.base import BaseCloudSyncer
from apps.cloud_platform.sync.registry import register_syncer
from apps.cloud_platform.sync.schemas import BalanceSyncData

logger = logging.getLogger(__name__)

try:
    from volcengine.ApiInfo import ApiInfo
    from volcengine.base.Service import Service
    from volcengine.Credentials import Credentials
    from volcengine.ServiceInfo import ServiceInfo

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning('火山引擎 SDK 未安装: pip install volcengine')

BILLING_API_VERSION = '2022-01-01'


@register_syncer
class VolcengineSyncer(BaseCloudSyncer):
    """火山引擎资源同步器 — 仅负责 API 数据拉取和格式转换。

    支持资源类型：
    - balance: 账户余额
    """

    PLATFORM_TYPE = 'volcengine'
    PLATFORM_NAMES = ['火山引擎', 'volcengine', 'volcano']
    SUPPORTED_RESOURCES = {'balance'}

    def __init__(self, cloud_platform) -> None:  # noqa: ANN001
        """初始化火山引擎同步器。

        Args:
            cloud_platform: CloudPlatform 模型实例。
        """
        super().__init__(cloud_platform)
        self._ak = ''
        self._sk = ''

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _setup(self) -> bool:
        """初始化 AK/SK 配置。

        Returns:
            True 表示配置有效，可以发起 API 调用。
        """
        if not SDK_AVAILABLE:
            return False
        creds = self.credentials
        self._ak = creds.get('access_key', '')
        self._sk = creds.get('access_secret', '')
        return bool(self._ak)

    def _build_billing_service(self) -> Service:
        """构建火山引擎账单查询客户端。

        Returns:
            配置好的 Service 实例，包含 QueryBalanceAcct API 定义。
        """
        service_info = ServiceInfo(
            'open.volcengineapi.com',
            {'Accept': 'application/json'},
            Credentials('', '', 'billing', 'cn-north-1'),
            5,
            5,
        )
        api_info = {
            'QueryBalanceAcct': ApiInfo(
                'POST',
                '/',
                {'Action': 'QueryBalanceAcct', 'Version': BILLING_API_VERSION},
                {},
                {},
            ),
        }
        service = Service(service_info, api_info)
        service.set_ak(self._ak)
        service.set_sk(self._sk)
        return service

    # ------------------------------------------------------------------
    # 账户余额
    # ------------------------------------------------------------------

    def _fetch_balance(self) -> BalanceSyncData | None:
        """获取火山引擎账户余额（幂等：同参数多次调用返回相同数据）。

        QueryBalanceAcct 接口无需额外请求参数，直接返回主账户余额信息。

        Returns:
            BalanceSyncData 实例，失败返回 None。
        """
        if not self._setup():
            return None
        try:
            service = self._build_billing_service()
            resp_text = service.post('QueryBalanceAcct', {}, {})
            if not resp_text:
                logger.warning('火山引擎余额接口返回空响应')
                return None

            data = json.loads(resp_text)

            # 检查业务错误
            metadata = data.get('ResponseMetadata', {})
            if metadata.get('Error'):
                err = metadata['Error']
                logger.error(
                    '火山引擎余额查询接口返回错误: [%s] %s',
                    err.get('Code', ''),
                    err.get('Message', ''),
                )
                return None

            result = data.get('Result', {})
            if not result:
                logger.warning('火山引擎余额响应中无 Result 字段')
                return None

            # 金额字段均为 String 类型，单位为元
            available = self._parse_amount(result.get('AvailableBalance', '0'))
            cash = self._parse_amount(result.get('CashBalance'))
            credit = self._parse_amount(result.get('CreditLimit'))
            frozen = self._parse_amount(result.get('FreezeAmount'))

            logger.info(
                '火山引擎余额: 可用=%s 现金=%s 信控=%s 冻结=%s',
                available,
                cash if cash is not None else '-',
                credit if credit is not None else '-',
                frozen if frozen is not None else '-',
            )

            return BalanceSyncData(
                total_balance=available or Decimal('0'),
                cash_balance=cash,
                credit_balance=credit,
                frozen_amount=frozen,
                currency='CNY',
                recorded_at=datetime.now(UTC),
            )

        except json.JSONDecodeError:
            logger.exception('火山引擎余额响应 JSON 解析失败')
            return None
        except Exception:
            logger.exception('火山引擎账户余额拉取失败')
            return None

    @staticmethod
    def _parse_amount(value: object) -> Decimal | None:
        """将 SDK 返回的金额字符串解析为 Decimal。

        Args:
            value: 金额值，可能为字符串或 None。

        Returns:
            Decimal 值，解析失败或空值返回 None。
        """
        if value is None:
            return None
        try:
            cleaned = str(value).strip().replace(',', '')
            if not cleaned:
                return None
            return Decimal(cleaned)
        except (ValueError, TypeError):
            return None
