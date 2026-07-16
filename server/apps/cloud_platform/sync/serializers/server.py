"""云服务器同步序列化器 — 封装 CloudServer 模型的所有数据库操作。

提供幂等的 upsert 方法，按 instance_id + platform 或 name + platform 匹配。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.cloud_platform.sync.resolvers.os_resolver import OSResolver
from apps.cloud_platform.sync.resolvers.status_resolver import StatusResolver

if TYPE_CHECKING:
    from apps.asset.models import CloudServer
    from apps.cloud_platform.models import CloudPlatform
    from apps.cloud_platform.sync.schemas import ServerSyncData, SyncResult

logger = logging.getLogger(__name__)


class CloudServerSyncSerializer:
    """云服务器同步序列化器。

    封装 CloudServer 模型的查询、创建和更新逻辑。
    每次 upsert 操作通过 DRF Serializer 进行数据校验和持久化。
    每个 Agent 持有独立实例，确保写入权限独立。
    """

    def __init__(self, platform: 'CloudPlatform') -> None:
        """初始化。

        Args:
            platform: 当前同步的云平台实例。
        """
        self.platform = platform

    def upsert(self, data: 'ServerSyncData', result: 'SyncResult') -> None:
        """新增或更新云服务器记录（幂等）。

        匹配策略：
        1. 优先按 instance_id + platform 匹配
        2. 回退按 name + platform 匹配

        Args:
            data: 服务器同步数据（Pydantic 模型）。
            result: 同步结果对象，累加 created/updated 计数。
        """
        from apps.asset.models import CloudServer
        from apps.asset.serializers import CloudServerSerializer

        serializer_data = self._build_serializer_data(data)

        # 幂等查找：instance_id 优先，name 回退
        server = self._find_existing(data)
        if server:
            s = CloudServerSerializer(server, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
            logger.debug('更新云服务器: %s (%s)', data.hostname, data.instance_id)
        else:
            s = CloudServerSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            s.save()
            result.created += 1
            logger.debug('新增云服务器: %s (%s)', data.hostname, data.instance_id)

    def bulk_upsert(self, data_list: list['ServerSyncData'], result: 'SyncResult') -> None:
        """批量 upsert 云服务器记录。

        Args:
            data_list: 服务器同步数据列表。
            result: 同步结果对象。
        """
        for data in data_list:
            try:
                self.upsert(data, result)
            except Exception:
                logger.exception('批量同步云服务器失败: %s', data.hostname)
                result.add_error(data.hostname, '服务器同步异常')

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _find_existing(self, data: 'ServerSyncData') -> 'CloudServer | None':
        """按 instance_id 或 name 查找已有记录。

        Args:
            data: 服务器同步数据。

        Returns:
            已有 CloudServer 实例或 None。
        """
        from apps.asset.models import CloudServer

        if data.instance_id:
            server = CloudServer.objects.filter(
                instance_id=data.instance_id,
                platform=self.platform,
            ).first()
            if server:
                return server

        if data.hostname:
            return CloudServer.objects.filter(
                name=data.hostname,
                platform=self.platform,
            ).first()

        return None

    def _build_serializer_data(self, data: 'ServerSyncData') -> dict:
        """将 Pydantic 同步数据转换为 DRF Serializer 所需字典。

        Args:
            data: 服务器同步数据。

        Returns:
            DRF Serializer 可接受的 data 字典。
        """
        serializer_data: dict = {
            'platform': str(self.platform.pk),
            'name': data.hostname or '',
            'os_type': OSResolver.resolve(data.os),
            'status': StatusResolver.resolve(data.status),
            'is_active': data.status != 'terminated',
        }

        if data.instance_id:
            serializer_data['instance_id'] = data.instance_id
        if data.cpu_cores is not None:
            serializer_data['cpu'] = data.cpu_cores
        if data.memory_gb is not None:
            serializer_data['memory'] = int(data.memory_gb)
        if data.disk_gb is not None:
            serializer_data['disk_size'] = int(data.disk_gb)
        if data.public_ips:
            serializer_data['public_ip'] = data.public_ips[0]
        if data.private_ips:
            serializer_data['private_ip'] = data.private_ips[0]
        if data.expire_date:
            serializer_data['expire_time'] = data.expire_date
        if data.region:
            serializer_data['region'] = data.region
        if data.tags:
            serializer_data['tags'] = data.tags
        if data.os_version:
            serializer_data['os_version'] = data.os_version

        return serializer_data
