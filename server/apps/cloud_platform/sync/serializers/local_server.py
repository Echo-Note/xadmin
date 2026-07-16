"""vSphere 物理宿主机同步序列化器 — 封装 LocalServer 模型的数据库操作。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.resolvers.os_resolver import OSResolver
from apps.cloud_platform.sync.resolvers.status_resolver import StatusResolver

if TYPE_CHECKING:
    from apps.asset.models import LocalServer
    from apps.cloud_platform.sync.schemas import ServerSyncData, SyncResult

logger = logging.getLogger(__name__)


class LocalServerSyncSerializer:
    """vSphere 物理宿主机同步序列化器。

    封装 LocalServer 模型的查询、创建和更新逻辑。
    按 name + ip_address 唯一匹配。
    """

    def __init__(self, platform) -> None:  # noqa: ANN001
        """初始化。

        Args:
            platform: CloudPlatform 模型实例（vCenter 平台）。
        """
        self.platform = platform

    def upsert(self, data: ServerSyncData, result: SyncResult) -> LocalServer | None:
        """新增或更新物理宿主机记录（幂等）。

        匹配策略：按 name + hostname 在已同步范围内查找。

        Args:
            data: 服务器同步数据（Pydantic 模型），server_type='physical'。
            result: 同步结果对象。

        Returns:
            LocalServer 实例或 None。
        """
        from apps.asset.serializers import LocalServerSerializer

        serializer_data = self._build_serializer_data(data)

        # 幂等查找：按 name + platform_name 匹配
        server = self._find_existing(data)
        if server:
            s = LocalServerSerializer(server, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
            logger.debug('更新物理主机: %s', data.hostname)
        else:
            s = LocalServerSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            instance = s.save()
            result.created += 1
            logger.debug('新增物理主机: %s', data.hostname)
            return instance
        return server

    def _find_existing(self, data: ServerSyncData) -> LocalServer | None:
        """查找已有物理主机记录。

        Args:
            data: 服务器同步数据。

        Returns:
            已有 LocalServer 实例或 None。
        """
        from apps.asset.models import LocalServer

        # 优先按序列号（instance_id 在 vSphere 中可能是 moid）
        if data.instance_id:
            server = LocalServer.objects.filter(
                serial_number=data.instance_id,
            ).first()
            if server:
                return server

        # 回退：按名称和 IP 查找
        if data.hostname:
            server = LocalServer.objects.filter(
                name=data.hostname,
            ).first()
            if server:
                return server

        return None

    def _build_serializer_data(self, data: ServerSyncData) -> dict:
        """将 Pydantic 同步数据转换为 DRF Serializer 所需字典。

        Args:
            data: 服务器同步数据。

        Returns:
            DRF Serializer 可接受的 data 字典。
        """
        serializer_data: dict = {
            'name': data.hostname or '',
            'hostname': data.hostname or '',
            'os_type': OSResolver.resolve(data.os),
            'status': StatusResolver.resolve(data.status),
            'is_active': data.status != 'terminated',
        }

        if data.instance_id:
            serializer_data['serial_number'] = data.instance_id

        if data.cpu_cores is not None:
            serializer_data['cpu_total_threads'] = data.cpu_cores

        if data.memory_gb is not None:
            serializer_data['memory_total'] = int(data.memory_gb)

        # IP 地址：优先管理口 IP
        if data.private_ips:
            serializer_data['ip_address'] = data.private_ips[0]

        if data.public_ips:
            if 'ip_address' not in serializer_data:
                serializer_data['ip_address'] = data.public_ips[0]

        # 从 tags 中提取 CPU 型号
        if data.tags and 'cpu_model' in data.tags and data.tags['cpu_model']:
            serializer_data['cpu_model'] = data.tags['cpu_model']

        if data.os_version and data.os_version not in ('other', ''):
            serializer_data['os_version'] = data.os_version

        return serializer_data
