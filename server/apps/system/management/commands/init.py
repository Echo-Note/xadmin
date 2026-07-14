"""项目初始化命令，自动发现各应用的 fixtures 并执行初始化。

遍历 INSTALLED_APPS，对包含 fixtures/initialize.py 的应用自动执行 Initialize.run()。

Usage:
    python manage.py init                  # 初始化所有应用
    python manage.py init -app apps.cloud_platform  # 仅初始化指定应用
    python manage.py init -y               # 重置并重新初始化
"""

import importlib
import logging
import os

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _has_initialize_module(app_label: str) -> bool:
    """检查指定应用是否包含 fixtures/initialize.py 模块。

    Args:
        app_label: 应用标签（如 apps.cloud_platform）。

    Returns:
        模块存在返回 True。
    """
    try:
        app_config = django_apps.get_app_config(app_label.split('.')[-1])
        init_file = os.path.join(app_config.path, 'fixtures', 'initialize.py')
        return os.path.isfile(init_file)
    except LookupError:
        return False


def run_app_initializer(app_label: str, reset: bool = False) -> None:
    """导入应用的 Initialize 类并执行初始化。

    Args:
        app_label: 应用标签。
        reset: 是否重置已有数据。
    """
    module_path = f"{app_label}.fixtures.initialize"
    try:
        module = importlib.import_module(module_path)
        initializer = module.Initialize(reset=reset, app=app_label)
        initializer.run()
    except (ModuleNotFoundError, AttributeError) as e:
        logger.warning(f"跳过 {app_label}: {e}")


def run_all_initializers(reset: bool = False, assign_apps: list[str] = None) -> None:
    """遍历所有已安装应用，执行初始化。

    Args:
        reset: 是否重置已有数据。
        assign_apps: 指定要初始化的应用列表，为空则处理所有。
    """
    for app_config in django_apps.get_app_configs():
        app_label = app_config.name
        if assign_apps and app_label not in assign_apps:
            continue
        if not _has_initialize_module(app_label):
            continue
        run_app_initializer(app_label, reset=reset)


class Command(BaseCommand):
    """项目初始化命令。"""

    help = '自动发现各应用的 fixtures 并执行初始化数据导入'

    def add_arguments(self, parser) -> None:
        """添加命令行参数。"""
        parser.add_argument(
            '-app', '-A',
            nargs='*',
            type=str,
            default=[],
            help='指定要初始化的应用标签，如 -app apps.cloud_platform',
        )
        parser.add_argument(
            '-y', '-Y',
            nargs='*',
            help='重置已有数据并重新初始化',
        )

    def handle(self, *args, **options) -> None:
        """执行命令：发现并运行各应用的初始化器。"""
        reset = isinstance(options.get('y'), list) or isinstance(options.get('Y'), list)
        assign_apps = options.get('app') or []

        run_all_initializers(reset=reset, assign_apps=assign_apps or None)

        self.stdout.write(self.style.SUCCESS('应用初始化数据完成。'))
