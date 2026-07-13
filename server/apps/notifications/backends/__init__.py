"""通知后端包，定义通知发送后端枚举及客户端映射。"""

import importlib
from typing import List

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.notifications.backends.base import BackendBase
from apps.system.models import UserInfo

client_name_mapper: dict = {}


class BACKEND(models.TextChoices):
    """通知发送后端枚举。"""

    EMAIL = 'email', _('Email')
    SITE_MSG = 'site_msg', _('Site message')

    # DINGTALK = 'dingtalk', _('DingTalk')
    # SMS = 'sms', _('SMS')

    @property
    def client(self) -> type[BackendBase]:
        """返回当前后端对应的客户端类。"""
        return client_name_mapper[self]

    def get_account(self, user: UserInfo) -> str:
        """获取用户在该后端对应的账号信息。"""
        return self.client.get_account(user)

    @property
    def is_enable(self) -> bool:
        """判断当前后端是否启用。"""
        return self.client.is_enable()

    @classmethod
    def filter_enable_backends(cls, backends: List) -> list:
        """从给定后端列表中筛选出已启用的后端。"""
        enable_backends = [b for b in backends if cls(b).is_enable]
        return enable_backends


for b in BACKEND:
    m = importlib.import_module(f'.{b}', __package__)
    client_name_mapper[b] = m.backend
