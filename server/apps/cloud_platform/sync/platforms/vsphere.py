"""vSphere 同步器 — 虚拟机 + ESXi 宿主机。pyVmomi SDK。"""

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


def _is_private_ip(ip: str) -> bool:
    """判断是否为内网IP。"""
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


@register_syncer
class VsphereSyncer(BaseCloudSyncer):
    """vSphere 同步器 — 仅负责 API 数据拉取和格式转换。"""

    PLATFORM_TYPE = 'vcenter'
    PLATFORM_NAMES = ['vsphere', 'vmware vsphere', 'vcenter', 'vmware']
    SUPPORTED_RESOURCES = {'server'}

    def __init__(self, cloud_platform) -> None:  # noqa: ANN001, D107
        super().__init__(cloud_platform)
        self._si = None

    def _connect(self):  # noqa: ANN202
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
            logger.exception('vSphere连接失败')
            return None
        return self._si

    def _fetch_servers(self) -> list[ServerSyncData]:
        si = self._connect()
        if not si:
            return []
        results = []
        try:
            content = si.RetrieveContent()
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.VirtualMachine, vim.HostSystem], True
            )
            for obj in container.view:
                try:
                    if isinstance(obj, vim.VirtualMachine):
                        if obj.config and obj.config.template:
                            continue
                        name = obj.name or ''
                        status = POWER_MAP.get(obj.runtime.powerState if obj.runtime else '', 'unknown')
                        cpu = obj.config.hardware.numCPU if obj.config and obj.config.hardware else None
                        mem = (
                            int(obj.config.hardware.memoryMB / 1024)
                            if obj.config and obj.config.hardware and obj.config.hardware.memoryMB
                            else None
                        )
                        instance_id = obj.config.uuid if obj.config else ''
                        os_id = obj.config.guestId if obj.config else ''
                        os_type = 'other'
                        os_keywords = {
                            'centos': 'centos', 'rhel': 'rhel', 'redhat': 'rhel',
                            'ubuntu': 'ubuntu', 'debian': 'debian', 'windows': 'windows',
                        }
                        for k, v in os_keywords.items():
                            if k in (os_id or '').lower():
                                os_type = v
                                break
                        public_ips = []
                        private_ips = []
                        if obj.guest and obj.guest.net:
                            for net in obj.guest.net:
                                if net.ipConfig and net.ipConfig.ipAddress:
                                    for ip in net.ipConfig.ipAddress:
                                        if ip.ipAddress:
                                            if _is_private_ip(ip.ipAddress):
                                                private_ips.append(ip.ipAddress)
                                            else:
                                                public_ips.append(ip.ipAddress)
                        results.append(
                            ServerSyncData(
                                hostname=name,
                                instance_id=instance_id,
                                status=status,
                                os=os_type,
                                cpu_cores=cpu,
                                memory_gb=float(mem) if mem else None,
                                public_ips=public_ips,
                                private_ips=private_ips,
                            )
                        )
                    elif isinstance(obj, vim.HostSystem):
                        name = obj.name or ''
                        status = POWER_MAP.get(obj.runtime.powerState if obj.runtime else '', 'unknown')
                        cpu = (
                            obj.hardware.cpuInfo.numCpuThreads
                            if obj.hardware and obj.hardware.cpuInfo
                            else None
                        )
                        mem = (
                            int(obj.hardware.memorySize / (1024**3))
                            if obj.hardware and obj.hardware.memorySize
                            else None
                        )
                        public_ips = []
                        private_ips = []
                        if obj.config and obj.config.network and obj.config.network.vnic:
                            for vnic in obj.config.network.vnic:
                                if vnic.spec and vnic.spec.ip and vnic.spec.ip.ipAddress:
                                    ip = vnic.spec.ip.ipAddress
                                    if _is_private_ip(ip):
                                        private_ips.append(ip)
                                    else:
                                        public_ips.append(ip)
                        results.append(
                            ServerSyncData(
                                hostname=name,
                                instance_id='',
                                status=status,
                                os='other',
                                cpu_cores=cpu,
                                memory_gb=float(mem) if mem else None,
                                public_ips=public_ips,
                                private_ips=private_ips,
                            )
                        )
                except Exception:
                    pass
            container.Destroy()
        except Exception:
            logger.exception('vSphere资产遍历失败')
        return results

    def _fetch_domains(self) -> list:
        """vSphere 不支持域名同步。"""
        return []

    def _fetch_balance(self):  # noqa: ANN202
        """vSphere 不支持余额查询。"""
        raise NotImplementedError
