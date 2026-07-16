"""账户余额同步序列化器 — 封装 CloudPlatform 和 AccountBalance 模型的数据库操作。

每次余额同步同时更新 CloudPlatform 实时余额和 AccountBalance 每日快照。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.utils.timezone import now

if TYPE_CHECKING:
    from apps.cloud_platform.models import CloudPlatform
    from apps.cloud_platform.sync.schemas import BalanceSyncData

logger = logging.getLogger(__name__)


class BalanceSyncSerializer:
    """账户余额同步序列化器。

    封装 CloudPlatform 余额字段和 AccountBalance 快照的写入逻辑。
    每个 Agent 持有独立实例，确保写入权限独立。
    """

    def __init__(self, platform: 'CloudPlatform') -> None:
        """初始化。

        Args:
            platform: 当前同步的云平台实例。
        """
        self.platform = platform

    def save(self, data: 'BalanceSyncData') -> None:
        """保存账户余额到 CloudPlatform 和 AccountBalance 快照（幂等）。

        - 更新 CloudPlatform.account_balance + balance_updated_time
        - 写入/更新当天的 AccountBalance 每日快照

        Args:
            data: 余额同步数据（Pydantic 模型）。
        """
        from apps.cloud_platform.models import AccountBalance

        # 更新 CloudPlatform 实时余额
        self.platform.account_balance = data.total_balance
        self.platform.balance_updated_time = data.recorded_at or now()
        self.platform.save(update_fields=['account_balance', 'balance_updated_time'])

        # 写入每日快照（同一天内多次同步会更新同一条记录）
        today = (data.recorded_at or now()).date()
        AccountBalance.objects.update_or_create(
            platform=self.platform,
            record_date=today,
            defaults={'balance': data.total_balance},
        )

        logger.info(
            '平台 [%s] 余额更新: ¥%s (快照日期: %s)',
            self.platform.name,
            data.total_balance,
            today,
        )
