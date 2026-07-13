"""同步模型字段的管理命令。"""

from django.core.management.base import BaseCommand

from apps.system.utils.modelfield import sync_model_field


class Command(BaseCommand):
    """同步模型字段标签的 Django 管理命令。"""

    help = 'Sync Model Field'

    def handle(self, *args, **options) -> None:
        """执行同步模型字段操作。"""
        sync_model_field()
