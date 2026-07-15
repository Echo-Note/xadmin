"""资产管理应用的枚举 choices 定义。"""

from django.db import models


class AssetSourceChoices(models.TextChoices):
    """资产来源枚举：云端 vs 本地。"""

    CLOUD = 'cloud', '云端资产'
    LOCAL = 'local', '本地资产'


class ServerOSTypeChoices(models.TextChoices):
    """服务器操作系统类型枚举。"""

    LINUX = 'linux', 'Linux'
    WINDOWS = 'windows', 'Windows'
    CENTOS = 'centos', 'CentOS'
    UBUNTU = 'ubuntu', 'Ubuntu'
    DEBIAN = 'debian', 'Debian'
    RHEL = 'rhel', 'RHEL'
    COREOS = 'coreos', 'CoreOS'
    OTHER = 'other', '其他'


class ServerStatusChoices(models.TextChoices):
    """服务器运行状态枚举。"""

    RUNNING = 'running', '运行中'
    STOPPED = 'stopped', '已停止'
    STARTING = 'starting', '启动中'
    STOPPING = 'stopping', '停止中'
    REBOOTING = 'rebooting', '重启中'
    PENDING = 'pending', '创建中'
    TERMINATED = 'terminated', '已销毁'
    UNKNOWN = 'unknown', '未知'


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


class HypervisorTypeChoices(models.TextChoices):
    """虚拟化平台类型枚举。"""

    VMWARE = 'vmware', 'VMware vSphere'
    KVM = 'kvm', 'KVM'
    HYPERV = 'hyperv', 'Hyper-V'
    XEN = 'xen', 'Xen'
    PROXMOX = 'proxmox', 'Proxmox VE'
    XCPNG = 'xcpng', 'XCP-ng'
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
