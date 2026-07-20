"""域名管理 — 菜单初始化脚本。

通过 MenuInitSerializer 序列化器读取 fixtures/init_menu.json 中
定义的菜单树结构，递归创建 MenuMeta 和 Menu 记录。

Usage:
    uv run python -m apps.domain.fixtures.initialize
"""

import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
django.setup()

from apps.system.fixtures.core_initialize import CoreInitialize  # noqa: E402
from apps.system.fixtures.initSerializer import MenuInitSerializer  # noqa: E402


class Initialize(CoreInitialize):
    """域名管理菜单初始化。"""

    def init_menu(self) -> None:
        """初始化域名管理菜单及权限。

        使用 clear_first=True：先清除所有 fixture 中的菜单记录再重建，
        确保 JSON 中已删除的旧菜单/权限项不会残留在数据库中。
        """
        self.init_base(
            MenuInitSerializer,
            unique_fields=['name'],
            clear_first=True,
        )

    def run(self) -> None:
        """执行初始化。"""
        self.init_menu()


if __name__ == '__main__':
    Initialize(app='apps.domain').run()
