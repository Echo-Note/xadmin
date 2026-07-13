"""消息推送与 WebSocket 通道工具函数。"""
#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : utils
# author : ly_13
# date : 3/6/2024
import asyncio
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.common.cache.storage import WebSocketMsgResultCache

channel_layer = get_channel_layer()


@async_to_sync
async def get_online_info() -> tuple[list[int], list[str]]:
    """获取所有在线用户的主键列表与通道列表。

    Returns:
        包含在线用户主键列表和通道名称列表的元组。
    """
    online_user_pks = []
    online_user_sockets = []
    for group in await channel_layer.get_groups():
        online_user_pks.append(int(group.split('_')[-1]))
        online_user_sockets.extend(await get_layers_form_group(group))
    return online_user_pks, online_user_sockets


def get_user_layer_group_name(user_pk: int | str) -> str:
    """根据用户主键生成对应的通道层组名称。

    Args:
        user_pk: 用户主键。

    Returns:
        用户通道层组名称字符串。
    """
    return f"{settings.CACHE_KEY_TEMPLATE.get('websocket_group_key')}_{user_pk}"


async def async_push_message(user_pk: str | int, message: dict, message_type: str = 'push_message') -> None:
    """异步向指定用户组推送消息。

    Args:
        user_pk: 用户主键。
        message: 待推送的消息字典。
        message_type: 消息类型，默认为 push_message。
    """
    await channel_layer.group_send(get_user_layer_group_name(user_pk), {'type': message_type, 'data': message})


async def get_layers_form_group(group: str) -> list[str]:
    """获取指定组中所有活跃通道列表。

    Args:
        group: 组名称。

    Returns:
        该组中所有活跃通道名称的列表。
    """
    return await channel_layer.get_layers(group)


@async_to_sync
async def get_online_user_layers(user_pk: int | str) -> list[str]:
    """获取指定用户所在组的所有活跃通道列表。

    Args:
        user_pk: 用户主键。

    Returns:
        用户组中所有活跃通道名称的列表。
    """
    return await get_layers_form_group(get_user_layer_group_name(user_pk))


@async_to_sync
async def get_online_users() -> list[int]:
    """获取所有在线用户的主键列表。

    Returns:
        在线用户主键列表。
    """
    return [int(group.split('_')[-1]) for group in await channel_layer.get_groups()]


async def async_push_layer_message(channel_name: str, message: dict, message_type: str = 'push_message') -> None:
    """异步向指定通道推送消息。

    Args:
        channel_name: 通道名称。
        message: 待推送的消息字典。
        message_type: 消息类型，默认为 push_message。
    """
    await channel_layer.send(channel_name, {'type': message_type, "data": message})


@async_to_sync
async def send_logout_msg(user_pk: str | int, channel_names: list[str] = None) -> None:
    """向指定用户的所有通道发送登出消息并从组中移除。

    Args:
        user_pk: 用户主键。
        channel_names: 通道名称列表，为空时自动查询该用户所在组的通道。
    """
    group_name = get_user_layer_group_name(user_pk)
    if not channel_names:
        channel_names = await get_layers_form_group(group_name)
    if channel_names:
        for channel_name in channel_names:
            await async_push_layer_message(channel_name, {"message_type": "logout"})
            await channel_layer.group_discard(group_name, channel_name)


@async_to_sync
async def push_message(user_pk: str | int, message: dict, message_type: str = 'push_message') -> None:
    """向指定用户推送消息（同步封装）。

    Args:
        user_pk: 用户主键。
        message: 待推送的消息字典。
        message_type: 消息类型，默认为 push_message。
    """
    return await async_push_message(user_pk, message, message_type)


async def wait_for_mid_result(mid: str) -> dict:
    """轮询等待指定消息 ID 的返回结果。

    Args:
        mid: 消息 ID。

    Returns:
        缓存中该消息 ID 对应的返回结果。
    """
    mid_cache = WebSocketMsgResultCache(mid)
    while True:
        if result := mid_cache.get_storage_cache():
            mid_cache.del_storage_cache()
            return result
        await asyncio.sleep(0.3)


def set_mid_result_to_cache(mid: str, content: dict, timeout: int = 10) -> None:
    """将消息 ID 对应的返回结果写入缓存。

    Args:
        mid: 消息 ID。
        content: 待缓存的消息内容。
        timeout: 缓存超时时间（秒），默认为 10。
    """
    WebSocketMsgResultCache(mid).set_storage_cache(content, timeout)


@async_to_sync
async def push_message_and_wait_result(channel_name: str, message: dict, message_type: str = 'push_message',
                                       mid: str = None, timeout: int = 5) -> dict:
    """向指定通道推送消息并等待返回结果。

    客户端返回结果必须和发送的 mid 一致，否则拿不到数据。

    Args:
        channel_name: 通道名称。
        message: 待推送的消息字典。
        message_type: 消息类型，默认为 push_message。
        mid: 消息 ID，为空时自动生成。
        timeout: 等待超时时间（秒），默认为 5。

    Returns:
        客户端返回的结果。
    """
    if mid is None:
        mid = uuid.uuid4().hex
    await channel_layer.send(channel_name, {'type': message_type, "data": message, 'mid': mid})
    try:
        return await asyncio.wait_for(wait_for_mid_result(mid), timeout=timeout)
    except TimeoutError:
        raise TimeoutError(_("Wait for result timeout"))
