"""WebSocket 异步 JSON 消息基础 Consumer。"""
#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : base
# author : ly_13
# date : 3/27/2025
import asyncio
import datetime
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils.translation import gettext_lazy as _
from rest_framework.utils import encoders

from apps.common.decorators import cached_method
from apps.common.utils import get_logger
from apps.message.utils import set_mid_result_to_cache
from apps.system.models import UserInfo
from apps.system.serializers.userinfo import UserInfoSerializer

logger = get_logger(__name__)


@database_sync_to_async
@cached_method()
def get_userinfo(user: UserInfo) -> dict:
    """获取用户的序列化信息。

    Args:
        user: 用户对象。

    Returns:
        用户信息序列化后的字典。
    """
    result = UserInfoSerializer(instance=user).data
    return result


class AsyncJsonWebsocket(AsyncWebsocketConsumer):
    """异步 WebSocket JSON 消息基类，提供 JSON 编解码与消息分发能力。"""

    user: None
    group_name: str

    @classmethod
    async def encode_json(cls, content: dict) -> str:
        """将内容编码为 JSON 字符串。

        Args:
            content: 待编码的字典内容。

        Returns:
            JSON 格式的字符串。
        """
        return json.dumps(content, cls=encoders.JSONEncoder, ensure_ascii=False)

    async def send_json(self, content: dict, close: bool = False) -> None:
        """将内容编码为 JSON 并发送给客户端。

        Args:
            content: 待发送的字典内容。
            close: 发送后是否关闭连接。
        """
        await super().send(text_data=await self.encode_json(content), close=close)

    @classmethod
    async def decode_json(cls, text_data: str) -> dict:
        """将 JSON 字符串解码为字典。

        Args:
            text_data: JSON 格式的字符串。

        Returns:
            解码后的字典。
        """
        return json.loads(text_data)

    async def receive_json(self, action: str, data: dict, content: dict, **kwargs) -> None:
        """处理接收到的 JSON 消息，由子类实现具体逻辑。

        数据格式如下：
        {
            "action": "chat_message",
            "data": ""
        }

        Args:
            action: 消息动作。
            data: 消息数据。
            content: 完整的原始消息内容。
        """
        pass

    async def receive_bytes(self, bytes_data: bytes, **kwargs) -> None:
        """处理接收到的二进制消息，由子类实现具体逻辑。

        Args:
            bytes_data: 接收到的二进制数据。
        """
        pass

    async def send_base_json(self, action: str, data: dict = None, mid: str = None, code: int = 1000,
                             detail: str = None, close: bool = False, **kwargs) -> None:
        """发送基础 JSON 消息，包含动作、数据、消息 ID 等字段。

        action: 动作
        data: 数据
        mid: 消息ID，该ID和发送端的mid保持一致

        Args:
            action: 消息动作。
            data: 消息数据。
            mid: 消息 ID，与发送端保持一致。
            code: 状态码，1000 表示成功。
            detail: 详情描述。
            close: 发送后是否关闭连接。
        """
        content = {
            'code': code,
            'action': action,
            'detail': detail if detail else (_("Operation successful") if code == 1000 else _("Operation failed")),
            'timestamp': str(datetime.datetime.now()),
        }
        if data:
            content['data'] = data
        if mid:
            content['mid'] = mid
        content.update(kwargs)
        await self.send_json(content, close)

    async def receive(self, text_data: str = None, bytes_data: bytes = None, **kwargs) -> None:
        """接收 WebSocket 消息并分发到对应的处理方法。

        Args:
            text_data: 文本消息。
            bytes_data: 二进制消息。
        """
        if text_data:
            try:
                content = await self.decode_json(text_data)
            except Exception as e:
                logger.error("failed to decode json", exc_info=e)
                return
            action = content.get('action')
            if not action:
                logger.error(f"action not exists. so close. {content}")
                await asyncio.sleep(3)
                await self.close()
            if mid := content.get('mid'):
                set_mid_result_to_cache(mid, content)
            data = content.get('data', {})
            match action:
                case 'ping' | 'userinfo' | 'push_message':
                    await self.channel_layer.send(self.channel_name, {"type": action, "data": data})
                case _:
                    await self.receive_json(action, data, content, **kwargs)
            return
        if bytes_data:
            return await self.receive_bytes(bytes_data, **kwargs)

        raise ValueError("No text section for incoming WebSocket frame!")

    async def _send_base(self, event: dict) -> None:
        """根据事件数据发送基础 JSON 消息。

        Args:
            event: 包含 type 和 data 的事件字典。
        """
        data = event['data']
        if isinstance(data, str):
            await self.send_base_json(event["type"], data, mid=event.get("mid"))
        else:
            await self.send_base_json(data.get("action", event["type"]), data, mid=data.get("mid", event.get("mid")))

    async def ping(self, event: dict) -> None:
        """处理 ping 消息，更新活跃层并返回 pong。

        Args:
            event: 包含 type 和 data 的事件字典。
        """
        await self.channel_layer.update_active_layers(self.group_name, self.channel_name)
        event['data'] = 'pong'
        await self._send_base(event)

    async def userinfo(self, event: dict) -> None:
        """处理 userinfo 消息，返回当前用户信息。

        Args:
            event: 包含 type 和 data 的事件字典。
        """
        event['data'] = await get_userinfo(self.user)
        await self._send_base(event)

    # 系统推送消息到客户端，推送消息格式如下：{"timestamp": 1709714533.5625794, "action": "push_message", "data": {"message_type": 11}}
    async def push_message(self, event: dict) -> None:
        """处理系统推送消息，转发给客户端。

        Args:
            event: 包含 type 和 data 的事件字典。
        """
        await self._send_base(event)

    async def chat_message(self, event: dict) -> None:
        """处理聊天消息，转发给客户端。

        Args:
            event: 包含 type 和 data 的事件字典。
        """
        await self._send_base(event)
