"""短信通知后端。"""

from typing import List

from apps.common.sdk.sms.endpoint import SMS
from .base import BackendBase


class SMS(BackendBase):
    """短信通知后端，通过第三方 SDK 发送短信。"""

    account_field = 'phone'
    is_enable_field_in_settings = 'SMS_ENABLED'

    def __init__(self) -> None:
        """初始化短信客户端。"""
        self.client = SMS()

    def send_msg(self, users: List, sign_name: str, template_code: str, template_param: dict) -> str | None:
        """向用户发送短信通知。

        Args:
            users: 接收用户列表。
            sign_name: 短信签名。
            template_code: 短信模板编号。
            template_param: 模板参数。

        Returns:
            短信发送结果。
        """
        accounts, __, __ = self.get_accounts(users)
        if not accounts:
            return
        return self.client.send_sms(accounts, sign_name, template_code, template_param)


backend = SMS
