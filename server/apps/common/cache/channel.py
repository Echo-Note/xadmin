#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : channel
# author : ly_13
# date : 3/29/2025
"""自定义 Redis 频道层，支持 channel 心跳过期与活跃层管理。"""

import time

from channels_redis.core import RedisChannelLayer as _RedisChannelLayer


class RedisChannelLayer(_RedisChannelLayer):
    """基于 Redis 的频道层扩展，提供 channel 自动过期与活跃层维护。"""

    layer_expire = 30  # 需要心跳方式发送在线状态，否则将channel移除

    async def group_discard(self, group: str, channel: str) -> None:
        """从指定组中移除 channel，若不存在则不做任何操作。"""
        assert self.valid_channel_name(channel), 'Channel name not valid'
        connection, key = await self.auto_expire_layers(group)
        await connection.zrem(key, channel)

    async def auto_expire_layers(self, group: str) -> tuple:
        """清理过期 channel 并返回连接与组键。

        Args:
            group: 组名称。

        Returns:
            元组 (Redis 连接, 组键)。
        """
        assert self.valid_group_name(group), 'Group name not valid'
        key = self._group_key(group)
        connection = self.connection(self.consistent_hash(group))

        # Discard old channels based on group_expiry
        await connection.zremrangebyscore(
            key, min=0, max=int(time.time()) - self.layer_expire
        )

        return connection, key

    async def get_layers(self, group: str) -> list[str]:
        """获取指定组中所有活跃 channel 列表。

        Args:
            group: 组名称。

        Returns:
            channel 名称列表。
        """
        connection, key = await self.auto_expire_layers(group)
        return [x.decode('utf8') for x in await connection.zrange(key, 0, -1)]

    async def update_active_layers(self, group: str, channel: str) -> None:
        """更新指定组中 channel 的活跃时间戳，并刷新过期时间。"""
        connection, key = await self.auto_expire_layers(group)
        await connection.zadd(key, {channel: time.time()})
        await connection.expire(key, self.group_expiry)

    async def get_groups(self) -> list[str]:
        """扫描所有 Redis 节点，返回全部组名称列表。

        Returns:
            组名称列表。
        """
        groups = []
        group = self._group_key('*')
        for index in range(self.ring_size):
            connection = self.connection(index)
            cursor = 0
            while True:
                cursor, keys = await connection.scan(cursor, match=group)
                for key in keys:
                    groups.append(key.decode('utf8').split(':')[-1])
                if cursor == 0:
                    break
        return groups
