"""状态解析器 — 将云平台原始状态值映射为内部统一状态标识。"""

from __future__ import annotations


class StatusResolver:
    """服务器状态映射解析器。

    各云平台状态值差异大，此解析器提供统一的映射能力。
    支持静态方法调用，子类可通过继承覆盖默认映射表。
    """

    # 默认状态映射：{平台原始值（小写）: 统一标识}
    DEFAULT_STATUS_MAP: dict[str, str] = {
        # 腾讯云 CVM
        'running': 'running',
        'stopped': 'stopped',
        'starting': 'starting',
        'stopping': 'stopping',
        'rebooting': 'rebooting',
        'pending': 'pending',
        'terminated': 'terminated',
        # 阿里云 ECS
        'running': 'running',
        'stopped': 'stopped',
        'starting': 'starting',
        'stopping': 'stopping',
        'pending': 'pending',
        # 华为云 ECS
        'active': 'running',
        'shutoff': 'stopped',
        'reboot': 'rebooting',
        'hard_reboot': 'rebooting',
        # vSphere
        'poweredon': 'running',
        'poweredoff': 'stopped',
        'suspended': 'stopped',
    }

    @classmethod
    def resolve(cls, raw_status: str) -> str:
        """将平台原始状态映射为统一标识。

        Args:
            raw_status: 云平台返回的原始状态字符串。

        Returns:
            统一状态标识（running/stopped/starting/stopping/rebooting/pending/terminated/unknown）。
        """
        if not raw_status:
            return 'unknown'
        key = raw_status.strip().lower()
        return cls.DEFAULT_STATUS_MAP.get(key, key if key in cls.DEFAULT_STATUS_MAP.values() else 'unknown')

    # 域名状态 → DomainStatusChoices 合法值的映射
    # 合法值：active/expired/pending/transferring/locked/forbidden/unverified/other
    DOMAIN_STATUS_MAP: dict[str, str] = {
        'pass': 'active',
        'run': 'active',
        'registered': 'active',
        'ok': 'active',
        'normal': 'active',
        'active': 'active',
        'pause': 'other',           # 暂停 → 无对应枚举值，归入 other
        'paused': 'other',
        'processing': 'pending',
        'waiting': 'pending',
        'transferring': 'transferring',
        'renewal process': 'pending',
        'deleted': 'expired',       # 已删除视为过期
        'expired': 'expired',
        'locked': 'locked',
        'forbidden': 'forbidden',
        'unverified': 'unverified',
        'pending': 'pending',
        'other': 'other',
    }

    @classmethod
    def resolve_domain_status(cls, raw_status: str) -> str:
        """将域名状态映射为 DomainStatusChoices 合法值。

        所有返回值保证在 Django DomainStatusChoices 枚举范围内：
        active / expired / pending / transferring / locked / forbidden / unverified / other

        Args:
            raw_status: 域名原始状态。

        Returns:
            统一域名状态（合法的 DomainStatusChoices 值）。
        """
        if not raw_status:
            return 'active'
        key = raw_status.strip().lower()
        return cls.DOMAIN_STATUS_MAP.get(key, 'other')


class TencentStatusResolver(StatusResolver):
    """腾讯云状态解析器。"""

    @classmethod
    def resolve(cls, raw_status: str) -> str:
        return {
            'RUNNING': 'running',
            'STOPPED': 'stopped',
            'STARTING': 'starting',
            'STOPPING': 'stopping',
            'REBOOTING': 'rebooting',
            'PENDING': 'pending',
            'TERMINATED': 'terminated',
        }.get(raw_status.upper() if raw_status else '', 'unknown')


class AliyunStatusResolver(StatusResolver):
    """阿里云状态解析器。"""

    @classmethod
    def resolve(cls, raw_status: str) -> str:
        return {
            'Running': 'running',
            'Stopped': 'stopped',
            'Starting': 'starting',
            'Stopping': 'stopping',
            'Pending': 'pending',
        }.get(raw_status or '', 'unknown')


class HuaweiStatusResolver(StatusResolver):
    """华为云状态解析器。"""

    @classmethod
    def resolve(cls, raw_status: str) -> str:
        return {
            'ACTIVE': 'running',
            'SHUTOFF': 'stopped',
            'REBOOT': 'rebooting',
            'HARD_REBOOT': 'rebooting',
        }.get(raw_status.upper() if raw_status else '', 'unknown')


class VsphereStatusResolver(StatusResolver):
    """vSphere 状态解析器。"""

    @classmethod
    def resolve(cls, raw_status: str) -> str:
        return {
            'poweredOn': 'running',
            'poweredOff': 'stopped',
            'suspended': 'stopped',
        }.get(raw_status or '', 'unknown')
