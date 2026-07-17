"""区域解析器 — 解析 cloud_platform.region 为区域列表。

支持 JSON 数组、逗号/空格/分号分隔的字符串格式。
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


class RegionResolver:
    """区域配置解析器。

    从 CloudPlatform.region 字段中解析出可迭代的区域标识列表。
    """

    @classmethod
    def parse(cls, raw_region: str | None, default_regions: list[str] | None = None) -> list[str]:
        """解析区域配置字符串为区域列表。

        支持格式：
        - JSON 数组：'["ap-guangzhou", "ap-shanghai"]'
        - 逗号分隔：'ap-guangzhou,ap-shanghai'
        - 分号分隔：'ap-guangzhou;ap-shanghai'
        - 空格分隔：'ap-guangzhou ap-shanghai'
        - 单个区域：'ap-guangzhou'

        Args:
            raw_region: CloudPlatform.region 字段值。
            default_regions: 解析失败或为空时的默认区域列表。

        Returns:
            区域标识字符串列表。
        """
        if not raw_region:
            return default_regions or []

        raw = raw_region.strip()

        # JSON 数组格式
        if raw.startswith('['):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(r) for r in parsed if r]
            except (json.JSONDecodeError, TypeError):
                logger.debug('区域配置 JSON 解析失败，尝试其他格式: %s', raw_region[:100])

        # 分隔符格式
        for sep in [',', ';']:
            if sep in raw:
                return [p.strip() for p in raw.split(sep) if p.strip()]

        # 空格分隔或单值
        parts = raw.split()
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]

        return [raw]

    @classmethod
    def get_default_for_platform(cls, platform_type: str) -> list[str]:
        """获取指定平台类型的默认区域列表。

        Args:
            platform_type: 平台类型标识。

        Returns:
            默认区域列表。
        """
        defaults = {
            'tencent': ['ap-guangzhou'],
            'aliyun': ['cn-hangzhou'],
            'huawei': ['cn-north-4'],
            'volcengine': ['cn-north-1'],
            'vcenter': ['default'],
            'meicheng': ['default'],
            'aws': ['us-east-1'],
            'azure': ['eastus'],
        }
        return defaults.get(platform_type, ['default'])
