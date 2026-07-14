# -*- coding: utf-8 -*-

"""
公司管理 — 菜单初始化脚本。

通过 MenuInitSerializer 序列化器读取 fixtures/init_menu.json 中
定义的菜单树结构，递归创建 MenuMeta 和 Menu 记录。

Usage:
    uv run python -m apps.company.fixtures.initialize
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")
django.setup()

from apps.system.fixtures.core_initialize import CoreInitialize
from apps.system.fixtures.initSerializer import MenuInitSerializer


class Initialize(CoreInitialize):
    """公司管理菜单初始化。"""

    def init_menu(self) -> None:
        """初始化公司管理菜单及权限。"""
        self.init_base(
            MenuInitSerializer,
            unique_fields=["name"],
        )

    def run(self) -> None:
        """执行初始化。"""
        self.init_menu()


if __name__ == "__main__":
    Initialize(app='apps.company').run()
