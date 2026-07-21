"""DNS 归属解析器 — 判断域名 DNS 是否由特定平台管理。"""

from __future__ import annotations


class DNSResolver:
    """DNS 服务平台归属判断。

    根据域名记录的 DNS 服务器特征判断 DNS 归属平台，
    避免将非本平台托管的 DNS 记录错误同步。
    """

    # 各平台 DNS 特征关键词映射
    PLATFORM_DNS_KEYWORDS: dict[str, list[str]] = {
        'tencent': ['dnspod', 'dnsv2', 'dnspod.net'],
        'aliyun': ['alidns', 'aliyuncs.com'],
        'huawei': ['huaweicloud', 'myhuaweicloud'],
        'meicheng': ['ezdnscenter', 'cndns'],
        'aws': ['awsdns', 'amazonaws.com'],
        'azure': ['azure', 'trafficmanager'],
    }

    @classmethod
    def is_managed_by(cls, dns_server: str, platform_type: str) -> bool:
        """判断 DNS 服务器是否由指定平台管理。

        Args:
            dns_server: 域名的 DNS 服务器列表字符串。
            platform_type: 平台类型标识。

        Returns:
            True 表示 DNS 由该平台托管。
        """
        keywords = cls.PLATFORM_DNS_KEYWORDS.get(platform_type, [])
        if not keywords:
            return True
        dns_lower = (dns_server or '').lower()
        return any(kw in dns_lower for kw in keywords)

    @classmethod
    def get_managed_platforms(cls, dns_server: str) -> list[str]:
        """获取 DNS 服务器可能归属的所有平台列表。

        Args:
            dns_server: 域名的 DNS 服务器列表字符串。

        Returns:
            匹配的平台类型列表。
        """
        matched: list[str] = []
        for platform_type, _keywords in cls.PLATFORM_DNS_KEYWORDS.items():
            if cls.is_managed_by(dns_server, platform_type):
                matched.append(platform_type)
        return matched
