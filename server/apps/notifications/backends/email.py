"""邮件通知后端。"""

from typing import List

from apps.common.tasks import send_mail_async
from .base import BackendBase


class Email(BackendBase):
    """邮件通知后端，通过异步任务发送邮件。"""

    account_field = 'email'
    is_enable_field_in_settings = 'EMAIL_ENABLED'

    def send_msg(self, users: List, message: str, subject: str) -> None:
        """向用户发送邮件通知。

        Args:
            users: 接收用户列表。
            message: 邮件正文（HTML）。
            subject: 邮件主题。
        """
        accounts, __, __ = self.get_accounts(users)
        if not accounts:
            return
        send_mail_async(subject, message, accounts, html_message=message)


backend = Email
