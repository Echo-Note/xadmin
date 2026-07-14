# -*- coding: utf-8 -*-

"""
菜单初始化序列化器。

通过序列化器处理菜单数据的创建/更新，遵循 Django REST Framework 标准流程。
借鉴 CloudHubOps dvadmin/system/fixtures/initSerializer.py 的 MenuInitSerializer 模式，
适配 xadmin 的 Menu（含 OneToOne MenuMeta）模型结构。
"""

from rest_framework import serializers

from apps.common.core.serializers import BaseModelSerializer
from apps.system.models import Menu, MenuMeta


class MenuMetaInitSerializer(BaseModelSerializer):
    """菜单元信息初始化序列化器。

    处理 MenuMeta 的创建与更新，在 MenuInitSerializer.save() 中被调用。
    """

    class Meta:
        """序列化器元数据。"""

        model = MenuMeta
        exclude = ['creator', 'modifier', 'id']
        read_only_fields = ['creator', 'modifier', 'dept_belong', 'id']


class MenuInitSerializer(BaseModelSerializer):
    """菜单初始化序列化器。

    支持递归创建/更新菜单树：
    - children：子菜单列表（含权限节点），在 save() 中递归处理
    - permissions：权限子节点列表，每个权限生成 menu_type=2 的 Menu 记录

    通过 Menu.name（唯一键）实现幂等：
    - 若已存在同名 Menu，则更新其字段及关联的 MenuMeta
    - 若不存在，则新建 Menu + MenuMeta
    """

    meta = MenuMetaInitSerializer(label='菜单元数据')
    children = serializers.ListField(child=serializers.DictField(), required=False, default=list, write_only=True)
    permissions = serializers.ListField(child=serializers.DictField(), required=False, default=list, write_only=True)

    class Meta:
        """序列化器元数据。"""

        model = Menu
        fields = [
            'pk', 'name', 'menu_type', 'rank', 'path', 'component',
            'method', 'is_active', 'meta', 'parent',
            'children', 'permissions',
        ]
        read_only_fields = ['pk']
        extra_kwargs = {
            'parent': {'required': False, 'allow_null': True},
            'component': {'required': False, 'allow_null': True, 'allow_blank': True},
            'method': {'required': False, 'allow_null': True, 'allow_blank': True},
            'is_active': {'required': False},
        }

    def validate(self, attrs: dict) -> dict:
        """校验数据完整性。

        Args:
            attrs: 待校验的属性字典。

        Returns:
            校验通过的属性字典。
        """
        menu_type = attrs.get('menu_type')
        if menu_type == Menu.MenuChoices.DIRECTORY:
            attrs.setdefault('component', '')
            attrs.pop('method', None)
        elif menu_type == Menu.MenuChoices.MENU:
            attrs.setdefault('method', None)
        elif menu_type == Menu.MenuChoices.PERMISSION:
            attrs.setdefault('component', None)
        return attrs

    # 非模型字段，需在 create/update 前从 validated_data 中移除
    EXTRA_FIELDS = {'children', 'permissions', 'reset'}

    def save(self, **kwargs) -> Menu:
        """保存菜单及递归处理子节点。

        流程：
        1. 通过 name 查找是否已存在同名 Menu
        2. 若存在则更新；不存在则创建（含 MenuMeta）
        3. 递归处理 children 和 permissions

        Returns:
            保存后的 Menu 实例。
        """
        name = self.validated_data.get('name')
        existing = Menu.objects.filter(name=name).first()

        if existing:
            instance = self._update_existing(existing)
        else:
            instance = self._create_new()

        # 递归处理子菜单
        children = self.initial_data.get('children', [])
        for child_data in children:
            child_data['parent'] = instance.pk
            self._process_child(child_data)

        # 处理权限子节点
        permissions = self.initial_data.get('permissions', [])
        for perm_data in permissions:
            perm_data['parent'] = instance.pk
            self._process_permission(perm_data)

        return instance

    def _clean_extra_fields(self, data: dict) -> dict:
        """过滤掉非模型字段，返回仅含 Menu 模型字段的字典。

        Args:
            data: 原始数据字典。

        Returns:
            过滤后的数据字典。
        """
        return {k: v for k, v in data.items() if k not in self.EXTRA_FIELDS}

    def _update_existing(self, existing: Menu) -> Menu:
        """更新已存在的 Menu 记录及其 MenuMeta。

        Args:
            existing: 已存在的 Menu 实例。

        Returns:
            更新后的 Menu 实例。
        """
        meta_data = self.validated_data.pop('meta', {})
        meta_serializer = MenuMetaInitSerializer(
            instance=existing.meta, data=meta_data, partial=True
        )
        meta_serializer.is_valid(raise_exception=True)
        meta_serializer.save()

        model_fields = self._clean_extra_fields(self.validated_data)
        for field_name, value in model_fields.items():
            if field_name in ('menu_type', 'rank', 'path', 'component', 'method', 'is_active', 'parent'):
                setattr(existing, field_name, value)
        existing.save()
        return existing

    def _create_new(self) -> Menu:
        """创建新的 Menu 及 MenuMeta。

        Returns:
            新创建的 Menu 实例。
        """
        meta_data = self.validated_data.pop('meta', {})
        meta_serializer = MenuMetaInitSerializer(data=meta_data)
        meta_serializer.is_valid(raise_exception=True)
        meta_instance = meta_serializer.save()

        model_fields = self._clean_extra_fields(self.validated_data)
        model_fields['meta'] = meta_instance
        return Menu.objects.create(**model_fields)

    def _process_child(self, child_data: dict) -> None:
        """递归处理子菜单节点。

        Args:
            child_data: 子菜单数据字典，已包含 parent。
        """
        child_name = child_data.get('name')
        existing = Menu.objects.filter(name=child_name).first()
        serializer = MenuInitSerializer(instance=existing, data=child_data, context=self.context)
        serializer.is_valid(raise_exception=True)
        serializer.save()

    def _process_permission(self, perm_data: dict) -> None:
        """处理权限子节点。

        Args:
            perm_data: 权限数据字典，已包含 parent。
        """
        perm_name = perm_data.get('name')
        existing = Menu.objects.filter(name=perm_name).first()
        serializer = MenuInitSerializer(instance=existing, data=perm_data, context=self.context)
        serializer.is_valid(raise_exception=True)
        serializer.save()
