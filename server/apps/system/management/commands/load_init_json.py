"""加载初始化 JSON 数据的管理命令。

执行流程：
1. 加载 loadjson/ 目录下的标准 fixture JSON 文件（MenuMeta, Menu, SystemConfig 等）
2. 自动调用各应用的 fixtures/initialize.py 执行自定义初始化
"""

import os.path

from django.conf import settings
from django.core.management.commands.loaddata import Command as LoadCommand
from django.db import DEFAULT_DB_ALIAS
from django.db.models.signals import ModelSignal
from django.core.management.base import CommandParser

from apps.settings.models import Setting
from apps.system.management.commands.init import run_all_initializers
from apps.system.models import *


class Command(LoadCommand):
    """加载初始化 JSON 数据的 Django 管理命令。"""

    help = 'load init json data'
    model_names = [MenuMeta, Menu, SystemConfig, DataPermission, UserRole, FieldPermission, ModelLabelField, DeptInfo,
                   Setting]
    missing_args_message = None

    def add_arguments(self, parser: CommandParser) -> None:
        """重写父类参数，不添加额外参数。

        Args:
            parser: 命令行参数解析器。
        """
        pass

    def handle(self, *args, **options) -> None:
        """执行加载命令，导入初始化 fixture 数据。

        加载前会检查是否已有用户，若没有则自动创建默认管理员。
        所有模型信号在加载期间被临时禁用。
        """
        ModelSignal.send = lambda *args, **kwargs: []  # 忽略任何信号

        # 加载 fixture 前检查是否已有用户，没有则自动创建默认管理员
        # fixture 中 creator_id=1 引用首个用户，必须确保该用户存在
        if not UserInfo.objects.exists():
            _ = UserInfo.objects.create_superuser('xadmin', 'xadmin@dvcloud.xin', 'xAdminPwd!')
            self.stdout.write(self.style.WARNING(
                'Created default admin user (username: xadmin, password: xAdminPwd!), please change it immediately.'))

        fixture_labels = []
        file_root = os.path.join(settings.PROJECT_DIR, "loadjson")
        for model in self.model_names:
            fixture_labels.append(os.path.join(file_root, f"{model._meta.model_name}.json"))
        options["ignore"] = ""
        options["database"] = DEFAULT_DB_ALIAS
        options["app_label"] = ""
        options["exclude"] = []
        options["format"] = "json"
        super(Command, self).handle(*fixture_labels, **options)

        # 加载完基础数据后，自动执行各应用的 fixtures 初始化
        self.stdout.write(self.style.NOTICE('正在执行各应用的 fixtures 初始化...'))
        run_all_initializers()
