"""vSphere 同步器 — 虚拟机 + ESXi 宿主机。pyVmomi SDK。

ESXi 物理宿主机对应 LocalServer 模型，虚拟机对应 LocalVM 模型。
虚拟机通过 host_server_name 字段关联宿主机。
"""

from __future__ import annotations

import logging
import ssl

from apps.cloud_platform.sync.base import BaseCloudSyncer
from apps.cloud_platform.sync.registry import register_syncer
from apps.cloud_platform.sync.schemas import ServerSyncData

logger = logging.getLogger(__name__)

try:
    from pyVim.connect import SmartConnect
    from pyVmomi import vim

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False
    logger.warning('pyVmomi 未安装: pip install pyvmomi')

POWER_MAP = {'poweredOn': 'running', 'poweredOff': 'stopped', 'suspended': 'stopped'}

# OS 关键词映射（vSphere guestId → 统一标识）
OS_KEYWORD_MAP: dict[str, str] = {
    'centos': 'centos',
    'rhel': 'rhel',
    'redhat': 'rhel',
    'ubuntu': 'ubuntu',
    'debian': 'debian',
    'windows': 'windows',
    'win': 'windows',
    'suse': 'suse',
    'coreos': 'coreos',
    'rocky': 'rockylinux',
    'alma': 'almalinux',
    'oracle': 'rhel',
    'esxi': 'other',
    'other': 'other',
}


def _is_private_ip(ip: str) -> bool:
    """判断是否为内网IP。

    Args:
        ip: IPv4 地址字符串。

    Returns:
        True 表示为内网 IP。
    """
    parts = ip.split('.')
    if len(parts) != 4:
        return True
    try:
        a, b = int(parts[0]), int(parts[1])
    except (ValueError, TypeError):
        return True
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    if a == 100 and 64 <= b <= 127:
        return True
    if a == 127:
        return True
    return False


def _resolve_os(guest_id: str) -> str:
    """根据 vSphere guestId 解析操作系统类型。

    Args:
        guest_id: vSphere 客户机操作系统标识。

    Returns:
        统一 OS 标识。
    """
    if not guest_id:
        return 'other'
    lower = guest_id.strip().lower()
    for keyword, label in sorted(OS_KEYWORD_MAP.items(), key=lambda x: -len(x[0])):
        if keyword in lower:
            return label
    return 'other'


def _extract_ips(obj) -> tuple[list[str], list[str]]:  # noqa: ANN001
    """从 vSphere 对象中提取 IP 地址并分类。

    Args:
        obj: VirtualMachine 或 HostSystem 对象。

    Returns:
        (public_ips, private_ips) 元组。
    """
    public_ips: list[str] = []
    private_ips: list[str] = []

    # VirtualMachine IP 提取
    if hasattr(obj, 'guest') and obj.guest and obj.guest.net:
        for net in obj.guest.net:
            if net.ipConfig and net.ipConfig.ipAddress:
                for ip in net.ipConfig.ipAddress:
                    if ip.ipAddress:
                        if _is_private_ip(ip.ipAddress):
                            if ip.ipAddress not in private_ips:
                                private_ips.append(ip.ipAddress)
                        else:
                            if ip.ipAddress not in public_ips:
                                public_ips.append(ip.ipAddress)

    # HostSystem IP 提取（管理口 vNIC）
    if isinstance(obj, vim.HostSystem) and obj.config and obj.config.network and obj.config.network.vnic:
        for vnic in obj.config.network.vnic:
            if vnic.spec and vnic.spec.ip and vnic.spec.ip.ipAddress:
                ip = vnic.spec.ip.ipAddress
                if _is_private_ip(ip):
                    if ip not in private_ips:
                        private_ips.append(ip)
                else:
                    if ip not in public_ips:
                        public_ips.append(ip)

    return public_ips, private_ips


@register_syncer
class VsphereSyncer(BaseCloudSyncer):
    """vSphere 同步器 — 仅负责 API 数据拉取和格式转换。

    拉取两类资产：
    - ESXi 物理宿主机 → server_type='physical' → LocalServer 模型
    - 虚拟机（排除模板） → server_type='virtual' → LocalVM 模型
    """

    PLATFORM_TYPE = 'vcenter'
    PLATFORM_NAMES = ['vsphere', 'vmware vsphere', 'vcenter', 'vmware']
    SUPPORTED_RESOURCES = {'server'}

    def __init__(self, cloud_platform) -> None:  # noqa: ANN001, D107
        super().__init__(cloud_platform)
        self._si = None

    def _connect(self):  # noqa: ANN202
        """建立到 vCenter/ESXi 的连接（带缓存）。"""
        if self._si:
            return self._si
        if not HAS_PYVMOMI:
            return None
        creds = self.credentials
        host = (self.cloud_platform.endpoint or '').strip()
        user = creds.get('username', '')
        pwd = creds.get('password', '')
        if not host or not user:
            return None
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            self._si = SmartConnect(host=host, user=user, pwd=pwd, sslContext=ctx)
        except Exception:
            logger.exception('vSphere 连接失败 [%s]', host)
            return None
        return self._si

    def _fetch_servers(self) -> list[ServerSyncData]:
        """拉取 vSphere 资产：宿主机 + 虚拟机。

        先遍历 HostSystem（物理主机），再遍历 VirtualMachine（虚拟机），
        虚拟机通过 host_server_name 关联其宿主机。

        Returns:
            ServerSyncData 列表，包含 physical 和 virtual 两种类型。
        """
        si = self._connect()
        if not si:
            return []

        results: list[ServerSyncData] = []
        try:
            content = si.RetrieveContent()
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.VirtualMachine, vim.HostSystem], True
            )

            # 第一遍：收集 ESXi 宿主机名称映射
            host_map: dict[str, str] = {}  # host_moid → host_name

            for obj in container.view:
                try:
                    if isinstance(obj, vim.HostSystem):
                        host_name = obj.name or ''
                        host_moid = getattr(obj, '_moId', '') or ''
                        if host_moid:
                            host_map[host_moid] = host_name

                        public_ips, private_ips = _extract_ips(obj)

                        cpu_cores = None
                        cpu_threads = None
                        cpu_model = ''
                        if obj.hardware and obj.hardware.cpuInfo:
                            cpu_cores = obj.hardware.cpuInfo.numCpuCores
                            cpu_threads = obj.hardware.cpuInfo.numCpuThreads
                            cpu_model = obj.hardware.cpuInfo.model or ''

                        memory_mb = None
                        if obj.hardware and obj.hardware.memorySize:
                            memory_mb = int(obj.hardware.memorySize / (1024**2))

                        status = POWER_MAP.get(
                            obj.runtime.powerState if obj.runtime else '',
                            'unknown',
                        )

                        # ESXi 宿主机不填 instance_id（无云平台实例ID）
                        # 使用 host_name 作为唯一标识
                        results.append(
                            ServerSyncData(
                                hostname=host_name,
                                instance_id=host_moid or host_name,
                                status=status,
                                os='other',  # ESXi 宿主机操作系统
                                os_version=cpu_model,  # 硬件型号作为补充信息
                                cpu_cores=cpu_threads or cpu_cores,
                                memory_gb=float(memory_mb) / 1024.0 if memory_mb else None,
                                public_ips=public_ips,
                                private_ips=private_ips,
                                server_type='physical',
                                tags={'cpu_model': cpu_model} if cpu_model else {},
                            )
                        )
                except Exception:
                    logger.exception('vSphere 宿主机遍历异常: %s', getattr(obj, 'name', 'unknown'))

            # 第二遍：虚拟机
            for obj in container.view:
                try:
                    if isinstance(obj, vim.VirtualMachine):
                        # 跳过模板
                        if obj.config and obj.config.template:
                            continue

                        vm_name = obj.name or ''
                        status = POWER_MAP.get(
                            obj.runtime.powerState if obj.runtime else '',
                            'unknown',
                        )

                        # CPU/内存
                        cpu = None
                        mem_gb = None
                        if obj.config and obj.config.hardware:
                            cpu = obj.config.hardware.numCPU
                            if obj.config.hardware.memoryMB:
                                mem_gb = int(obj.config.hardware.memoryMB / 1024)

                        # 实例 ID（vSphere VM UUID）
                        instance_id = obj.config.uuid if obj.config else ''

                        # OS 类型
                        guest_id = obj.config.guestId if obj.config else ''
                        os_type = _resolve_os(guest_id)

                        # IP 地址
                        public_ips, private_ips = _extract_ips(obj)

                        # 宿主机关联
                        host_name = ''
                        host_instance_id = ''
                        if obj.runtime and obj.runtime.host:
                            host_ref = obj.runtime.host
                            host_moid = getattr(host_ref, '_moId', '') or str(host_ref)
                            host_name = host_map.get(host_moid, '')
                            host_instance_id = host_moid

                        results.append(
                            ServerSyncData(
                                hostname=vm_name,
                                instance_id=instance_id,
                                status=status,
                                os=os_type,
                                os_version=guest_id,
                                cpu_cores=cpu,
                                memory_gb=float(mem_gb) if mem_gb else None,
                                public_ips=public_ips,
                                private_ips=private_ips,
                                server_type='virtual',
                                host_server_name=host_name,
                                host_server_instance_id=host_instance_id,
                            )
                        )
                except Exception:
                    logger.exception('vSphere 虚拟机遍历异常: %s', getattr(obj, 'name', 'unknown'))

            container.Destroy()
        except Exception:
            logger.exception('vSphere 资产遍历失败')
        return results

    def _fetch_domains(self) -> list:
        """vSphere 不支持域名同步。"""
        return []

    def _fetch_balance(self):  # noqa: ANN202
        """vSphere 不支持余额查询。"""
        raise NotImplementedError
