"""域名管理应用的枚举 choices 定义。

包含域名状态、DNS 记录类型、ICP 备案状态、ICP 预检测状态等枚举。
从 apps.asset.choices 迁移而来，仅保留域名相关枚举。
"""

from django.db import models


class DomainStatusChoices(models.TextChoices):
    """域名状态枚举。"""

    ACTIVE = 'active', '正常'
    EXPIRED = 'expired', '已过期'
    PENDING = 'pending', '注册中'
    TRANSFERRING = 'transferring', '转移中'
    LOCKED = 'locked', '已锁定'
    FORBIDDEN = 'forbidden', '已封禁'
    UNVERIFIED = 'unverified', '未实名'
    OTHER = 'other', '其他'


class DnsRecordTypeChoices(models.TextChoices):
    """DNS 记录类型枚举。"""

    A = 'A', 'A'
    AAAA = 'AAAA', 'AAAA'
    CNAME = 'CNAME', 'CNAME'
    MX = 'MX', 'MX'
    TXT = 'TXT', 'TXT'
    NS = 'NS', 'NS'
    SRV = 'SRV', 'SRV'
    CAA = 'CAA', 'CAA'
    OTHER = 'other', '其他'


class IcpFilingStatusChoices(models.TextChoices):
    """备案状态枚举，同时用于 ICP 备案和公安备案。"""

    NOT_FILED = 'not_filed', '未备案'
    FILED = 'filed', '已备案'
    PENDING_CONFIRM = 'pending_confirm', '待人工确认'
    CHANGING = 'changing', '变更中'


class IcpCheckStatusChoices(models.TextChoices):
    """ICP 备案预检测状态枚举。"""

    NOT_CHECKED = 'not_checked', '未检测'
    PASSED = 'passed', '检测通过'
    SUSPECTED_MISSING = 'suspected_missing', '疑似未悬挂'
    NO_WWW_RECORD = 'no_www_record', '无www解析'
    CHECK_FAILED = 'check_failed', '检测失败'
