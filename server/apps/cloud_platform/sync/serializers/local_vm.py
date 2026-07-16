"""vSphere 虚拟机同步序列化器 — 封装 LocalVM 模型的数据库操作。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.resolvers.os_resolver import OSResolver
from apps.cloud_platform.sync.resolvers.status_resolver import StatusResolver

if TYPE_CHECKING:
    from apps.asset.models import LocalServer, LocalVM
    from apps.cloud_platform.sync.schemas import ServerSyncData, SyncResult

logger = logging.getLogger(__name__)


class LocalVMSyncSerializer:
    """vSphere 虚拟机同步序列化器。

    封装 LocalVM 模型的查询、创建和更新逻辑。
    按 name + host_server 唯一匹配。
    依赖宿主机的 LocalServer 记录已存在。
    """

    def __init__(self, platform) -> None:  # noqa: ANN001
        """初始化。

        Args:
            platform: CloudPlatform 模型实例（vCenter 平台）。
        """
        self.platform = platform

    def upsert(self, data: ServerSyncData, result: SyncResult) -> LocalVM | None:
        """新增或更新虚拟机记录（幂等）。

        Args:
            data: 服务器同步数据（Pydantic 模型），server_type='virtual'。
            result: 同步结果对象。

        Returns:
            LocalVM 实例或 None（宿主机未找到时返回 None）。
        """
        from apps.asset.serializers import LocalVMSerializer

        # 查找宿主机
        host_server = self._find_host(data)
        if host_server is None:
            logger.warning(
                '虚拟机 %s 的宿主机 %s 未找到，跳过同步',
                data.hostname,
                data.host_server_name,
            )
            result.add_error(data.hostname, f'宿主机 {data.host_server_name} 未找到')
            return None

        serializer_data = self._build_serializer_data(data, host_server)

        # 幂等查找：按 name + host_server 匹配
        vm = self._find_existing(data, host_server)
        if vm:
            s = LocalVMSerializer(vm, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
            logger.debug('更新虚拟机: %s (宿主机: %s)', data.hostname, data.host_server_name)
        else:
            s = LocalVMSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            instance = s.save()
            result.created += 1
            logger.debug('新增虚拟机: %s (宿主机: %s)', data.hostname, data.host_server_name)
            return instance
        return vm

    def _find_host(self, data: ServerSyncData) -> LocalServer | None:
        """查找虚拟机归属的物理宿主机。

        优先按 host_server_instance_id（vSphere moid）匹配，回退按宿主名称。

        Args:
            data: 服务器同步数据。

        Returns:
            LocalServer 实例或 None。
        """
        from apps.asset.models import LocalServer

        if data.host_server_instance_id:
            host = LocalServer.objects.filter(
                serial_number=data.host_server_instance_id,
            ).first()
            if host:
                return host

        if data.host_server_name:
            host = LocalServer.objects.filter(
                name=data.host_server_name,
            ).first()
            if host:
                return host

        return None

    def _find_existing(self, data: ServerSyncData, host_server: LocalServer) -> LocalVM | None:
        """查找已有虚拟机记录。

        Args:
            data: 服务器同步数据。
            host_server: 宿主机实例。

        Returns:
            已有 LocalVM 实例或 None。
        """
        from apps.asset.models import LocalVM

        if data.instance_id:
            vm = LocalVM.objects.filter(
                vm_id=data.instance_id,
            ).first()
            if vm:
                return vm

        if data.hostname:
            vm = LocalVM.objects.filter(
                name=data.hostname,
                host_server=host_server,
            ).first()
            if vm:
                return vm

        return None

    def _build_serializer_data(self, data: ServerSyncData, host_server: LocalServer) -> dict:
        """将 Pydantic 同步数据转换为 DRF Serializer 所需字典。

        Args:
            data: 服务器同步数据。
            host_server: 宿主机实例。

        Returns:
            DRF Serializer 可接受的 data 字典。
        """
        serializer_data: dict = {
            'name': data.hostname or '',
            'host_server': str(host_server.pk),
            'os_type': OSResolver.resolve(data.os),
            'status': StatusResolver.resolve(data.status),
            'is_active': data.status != 'terminated',
            'hypervisor': 'vmware',
        }

        if data.instance_id:
            serializer_data['vm_id'] = data.instance_id

        if data.cpu_cores is not None:
            serializer_data['cpu'] = data.cpu_cores

        if data.memory_gb is not None:
            serializer_data['memory'] = int(data.memory_gb)

        if data.disk_gb is not None:
            serializer_data['disk_size'] = int(data.disk_gb)

        if data.private_ips:
            serializer_data['ip_address'] = data.private_ips[0]
        elif data.public_ips:
            serializer_data['ip_address'] = data.public_ips[0]

        if data.os_version:
            serializer_data['os_version'] = data.os_version

        return serializer_data
