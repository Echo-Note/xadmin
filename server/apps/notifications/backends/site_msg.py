"""站内信通知后端。"""

from typing import List

from apps.notifications.message import SiteMessageUtil as Client
from .base import BackendBase


class SiteMessage(BackendBase):
    """站内信通知后端，通过 SiteMessageUtil 发送站内消息。"""

    account_field = 'id'

    def send_msg(self, users: List, message: str, subject: str, **kwargs) -> None:
        """向用户发送站内信。

        Args:
            users: 接收用户列表。
            message: 消息正文。
            subject: 消息主题。
            **kwargs: 额外参数。
        """
        accounts, __, __ = self.get_accounts(users)
        Client.send_msg(subject, message, user_ids=accounts, **kwargs)

    @classmethod
    def is_enable(cls) -> bool:
        """站内信始终启用。"""
        return True


backend = SiteMessage
