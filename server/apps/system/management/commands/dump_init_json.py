"""导出初始化 JSON 数据的管理命令。"""

import os.path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.db.models import Model, QuerySet

from apps.settings.models import Setting
from apps.system.models import *


def get_fields(model: type[Model]) -> list[str]:
    """获取模型需要导出的字段名列表。

    Args:
        model: Django 模型类。

    Returns:
        需要导出的字段名列表。
    """
    if issubclass(model, FieldPermission):
        exclude_fields = ['updated_time', 'created_time']
    elif issubclass(model, ModelLabelField):
        exclude_fields = ['updated_time']
    else:
        exclude_fields = []

    return [x.name for x in model._meta.get_fields() if x.name not in exclude_fields]


class Command(BaseCommand):
    """导出初始化 JSON 数据的 Django 管理命令。"""

    help = 'dump init json data'
    model_names = [UserRole, DeptInfo, Menu, MenuMeta, SystemConfig, DataPermission, FieldPermission, ModelLabelField,
                   Setting]

    def save_json(self, queryset: QuerySet, filename: str) -> None:
        """将查询集序列化为 JSON 并写入文件。

        Args:
            queryset: 需要导出的模型查询集。
            filename: 输出文件路径。
        """
        stream = open(filename, 'w', encoding='utf8')
        try:
            serializers.serialize(
                'json',
                queryset,
                indent=2,
                stream=stream or self.stdout,
                object_count=queryset.count(),
                fields=get_fields(queryset.model)
            )
        except Exception as e:
            print(f"{queryset.model._meta.model_name} {filename} dump failed {e}")
        finally:
            if stream:
                stream.close()

    def handle(self, *args, **options) -> None:
        """执行导出命令，遍历所有配置的模型并导出为 JSON 文件。"""
        file_root = os.path.join(settings.PROJECT_DIR, "loadjson")
        for model in self.model_names:
            self.save_json(model.objects.all().order_by('pk'),
                           os.path.join(file_root, f"{model._meta.model_name}.json"))
