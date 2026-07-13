"""通知后端基类定义。"""

from typing import List, Tuple

from django.conf import settings

from apps.system.models import UserInfo


class BackendBase:
    """通知后端基类，提供账号获取与启用状态检查的通用方法。"""

    # User 表中的字段
    account_field: str | None = None

    # Django setting 中的字段名
    is_enable_field_in_settings: str | None = None

    def get_accounts(self, users: List) -> Tuple[list, list, dict]:
        """从用户列表中分离已绑定账号和未绑定账号的用户。

        Args:
            users: 用户对象列表。

        Returns:
            tuple: (已绑定账号列表, 未绑定用户列表, 账号到用户的映射)。
        """
        accounts = []
        unbound_users = []
        account_user_mapper = {}

        for user in users:
            account = getattr(user, self.account_field, None)
            if account:
                account_user_mapper[account] = user
                accounts.append(account)
            else:
                unbound_users.append(user)
        return accounts, unbound_users, account_user_mapper

    @classmethod
    def get_account(cls, user: UserInfo) -> str:
        """获取用户在此后端绑定的账号。"""
        return getattr(user, cls.account_field)

    @classmethod
    def is_enable(cls) -> bool:
        """判断此后端是否在 Django settings 中启用。"""
        enable = getattr(settings, cls.is_enable_field_in_settings)
        return bool(enable)
