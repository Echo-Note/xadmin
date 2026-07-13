"""菜单序列化器。"""

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import Menu, MenuMeta

logger = get_logger(__name__)


class MenuMetaSerializer(BaseModelSerializer):
    """菜单元信息序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = MenuMeta
        exclude = ['creator', 'modifier', 'id']
        read_only_fields = ['creator', 'modifier', 'dept_belong', 'id']

    pk = serializers.UUIDField(source='id', read_only=True)


class MenuSerializer(BaseModelSerializer):
    """菜单序列化器，嵌套元信息序列化。"""

    meta = MenuMetaSerializer(label=_('Menu meta'))

    class Meta:
        """序列化器元数据。"""

        model = Menu
        fields = [
            'pk', 'name', 'rank', 'path', 'component', 'meta', 'parent', 'menu_type', 'is_active', 'model', 'method'
        ]
        # read_only_fields = ['pk'] # 用于文件导入导出时，不丢失上级节点
        extra_kwargs = {
            'parent': {'attrs': ['pk', 'name'], 'allow_null': True, 'required': False},
            'model': {'attrs': ['pk', 'name', 'label'], 'allow_null': True, 'required': False},
        }

    def update(self, instance: Menu, validated_data: dict) -> Menu:
        """更新菜单及其元信息，在事务中执行。

        Args:
            instance: 待更新的 Menu 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 Menu 实例。
        """
        with transaction.atomic():
            serializer = MenuMetaSerializer(instance.meta, data=validated_data.pop('meta'), partial=True,
                                            context=self.context)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return super().update(instance, validated_data)

    def create(self, validated_data: dict) -> Menu:
        """创建菜单及其元信息，在事务中执行。

        Args:
            validated_data: 已验证的数据字典。

        Returns:
            创建的 Menu 实例。
        """
        with transaction.atomic():
            serializer = MenuMetaSerializer(data=validated_data.pop('meta'), context=self.context)
            serializer.is_valid(raise_exception=True)
            validated_data['meta'] = serializer.save()
            return super().create(validated_data)
