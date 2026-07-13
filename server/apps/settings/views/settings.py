#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : settings
# author : ly_13
# date : 7/31/2024
"""设置视图集定义，包含基础设置和系统设置管理。"""

from django.conf import settings
from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import NoDetailModelSet, ImportExportDataAction, ListDeleteModelSet
from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.settings.models import Setting
from apps.settings.serializers.basic import BasicSettingSerializer
from apps.settings.serializers.setting import SettingSerializer

logger = get_logger(__name__)


class BaseSettingViewSet(NoDetailModelSet):
    """设置视图基类，提供设置项的读取与更新。"""

    queryset = Setting.objects.all()
    serializer_class = BasicSettingSerializer
    category = "basic"
    serializer_class_mapper = {}

    def get_serializer_class(self) -> type:
        """根据分类映射返回对应的序列化器类。"""
        if not self.serializer_class_mapper:
            return super().get_serializer_class()
        self.category = self.request.query_params.get('category', 'basic')
        cls = self.serializer_class_mapper.get(self.category, self.serializer_class)
        return cls

    def get_fields(self) -> dict:
        """返回当前序列化器的所有字段。"""
        serializer = self.get_serializer_class()()
        fields = serializer.get_fields()
        return fields

    def get_object(self) -> dict:
        """从 Django settings 中获取所有字段值。"""
        items = self.get_fields().keys()
        obj = {}
        for item in items:
            if hasattr(settings, item):
                obj[item] = getattr(settings, item)
            else:
                obj[item] = None
        return obj

    def parse_serializer_data(self, serializer: BaseModelSerializer) -> list:
        """解析序列化器数据，生成设置项列表。

        Args:
            serializer: 序列化器实例。

        Returns:
            设置项字典列表。
        """
        data = []
        fields = self.get_fields()
        encrypted_items = [name for name, field in fields.items() if field.write_only]
        for name, value in serializer.validated_data.items():
            encrypted = name in encrypted_items
            if encrypted and value in ['', None]:
                continue
            data.append({
                'name': name, 'value': value,
                'encrypted': encrypted, 'category': self.category
            })
        return data

    def perform_update(self, serializer: BaseModelSerializer) -> None:
        """更新设置项，将变更写入数据库。

        Args:
            serializer: 序列化器实例。
        """
        post_data_names = list(self.request.data.keys())
        settings_items = self.parse_serializer_data(serializer)
        serializer_data = getattr(serializer, 'data', {})
        change_fields = []
        for item in settings_items:
            if item['name'] not in post_data_names:
                continue
            changed, setting = Setting.update_or_create(**item, user=self.request.user)
            if not changed:
                continue
            change_fields.append(setting.name)
            serializer_data[setting.name] = setting.cleaned_value
        setattr(serializer, '_data', serializer_data)
        setattr(serializer, '_change_fields', change_fields)
        if hasattr(serializer, 'post_save'):
            serializer.post_save()


class SettingFilter(BaseFilterSet):
    """系统设置过滤器。"""

    pk = filters.UUIDFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    value = filters.CharFilter(field_name='value', lookup_expr='icontains')

    class Meta:
        """元数据配置。"""

        model = Setting
        fields = ['pk', 'is_active', 'name', 'category', 'value']


class SettingViewSet(ListDeleteModelSet, ImportExportDataAction):
    """系统设置管理视图集。"""

    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    ordering_fields = ['created_time', 'category']
    filterset_class = SettingFilter
