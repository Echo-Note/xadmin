"""OS 类型解析器 — 将云平台操作系统名称映射为内部统一标识。"""

from __future__ import annotations


class OSResolver:
    """操作系统类型解析器。

    各云平台返回的 OS 名称格式不一，此解析器通过关键词匹配映射到统一标识。
    """

    # OS 关键词 → 统一标识
    OS_KEYWORD_MAP: dict[str, str] = {
        'linux': 'linux',
        'centos': 'centos',
        'ubuntu': 'ubuntu',
        'debian': 'debian',
        'rhel': 'rhel',
        'redhat': 'rhel',
        'red hat': 'rhel',
        'coreos': 'coreos',
        'windows': 'windows',
        'win': 'windows',
        'suse': 'suse',
        'freebsd': 'freebsd',
        'alma': 'almalinux',
        'rocky': 'rockylinux',
    }

    @classmethod
    def resolve(cls, os_name: str) -> str:
        """将 OS 名称映射为统一标识。

        按关键词匹配，优先匹配更长的关键词（如 "Red Hat" 优先于 "red"）。

        Args:
            os_name: 平台返回的原始操作系统名称。

        Returns:
            统一 OS 标识（linux/centos/ubuntu/debian/rhel/coreos/windows/suse/freebsd/almalinux/rockylinux/other）。
        """
        if not os_name:
            return 'other'
        lower = os_name.strip().lower()
        # 按关键词长度降序匹配，优先精确匹配
        for keyword, label in sorted(cls.OS_KEYWORD_MAP.items(), key=lambda x: -len(x[0])):
            if keyword in lower:
                return label
        return 'other'
