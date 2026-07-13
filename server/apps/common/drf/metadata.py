# -*- coding: utf-8 -*-
#
"""DRF 元数据扩展模块，提供带过滤与排序字段信息的 SimpleMetadata 扩展实现。"""


from __future__ import unicode_literals

import datetime
from collections import OrderedDict
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.utils.encoding import force_str
from rest_framework import exceptions, serializers
from rest_framework.fields import empty
from rest_framework.metadata import SimpleMetadata
from rest_framework.request import clone_request


class SimpleMetadataWithFilters(SimpleMetadata):
    """扩展 SimpleMetadata，增加过滤器与排序字段信息。"""

    methods = {"PUT", "POST", "GET", "PATCH"}
    attrs = [
        "read_only", "label", "help_text",
        "min_length", "max_length", "min_value",
        "max_value", "write_only"
    ]

    def determine_actions(self, request: Any, view: Any) -> dict:
        """对于基于类的通用视图，返回 PUT 和 POST 方法所接受字段的信息。

        Args:
            request: DRF 请求对象。
            view: 视图实例。

        Returns:
            以 HTTP 方法为键、字段信息为值的字典。
        """
        actions = {}
        view.raw_action = getattr(view, "action", None)
        for method in self.methods & set(view.allowed_methods):
            if hasattr(view, "action_map"):
                view.action = view.action_map.get(method.lower(), view.action)

            view.request = clone_request(request, method)
            try:
                # Test global permissions
                if hasattr(view, "check_permissions"):
                    view.check_permissions(view.request)
                # Test object permissions
                if method == "PUT" and hasattr(view, "get_object"):
                    view.get_object()
            except (exceptions.APIException, PermissionDenied, Http404):
                pass
            else:
                # If user has appropriate permissions for the view, include
                # appropriate metadata about the fields that should be supplied.
                serializer = view.get_serializer()
                actions[method] = self.get_serializer_info(serializer)
            finally:
                view.request = request
        return actions

    def get_field_type(self, field: Any) -> str:
        """根据序列化器字段返回表示字段类型的字符串。

        Args:
            field: 序列化器字段实例。

        Returns:
            字段类型标识字符串。
        """
        tp = getattr(field, 'input_type', None)
        if tp:
            return tp
        tp = self.label_lookup[field]

        class_name = field.__class__.__name__
        if class_name == "LabeledChoiceField":
            tp = "labeled_choice"
        if class_name == "LabeledMultipleChoiceField":
            tp = "labeled_multiple_choice"
        elif class_name == "JSONField":
            tp = 'json'
        elif class_name == "BasePrimaryKeyRelatedField":
            tp = "object_related_field"
        elif class_name == "ManyRelatedField":
            child_relation_class_name = field.child_relation.__class__.__name__
            if child_relation_class_name == "BasePrimaryKeyRelatedField":
                tp = "m2m_related_field"
        return tp

    @staticmethod
    def set_choices_field(field: Any, field_info: dict) -> None:
        """为字段信息字典填充选项列表。

        Args:
            field: 序列化器字段实例。
            field_info: 待填充的字段信息字典。
        """
        field_info["choices"] = [
            {
                "value": choice_value,
                "label": force_str(choice_label, strings_only=True),
            }
            for choice_value, choice_label in dict(field.choices).items()
        ]

    def get_field_info(self, field: Any) -> OrderedDict:
        """根据序列化器字段实例返回其元数据字典。

        Args:
            field: 序列化器字段实例。

        Returns:
            包含字段元数据的有序字典。
        """
        field_info = OrderedDict()
        field_info["type"] = self.get_field_type(field)
        field_info["required"] = getattr(field, "required", False)

        # Default value
        default = getattr(field, "default", None)
        if default is not None and default != empty:
            if isinstance(default, (str, int, bool, float, datetime.datetime, list)):
                field_info["default"] = default

        for attr in self.attrs:
            value = getattr(field, attr, None)
            if value is not None and value != "":
                field_info[attr] = force_str(value, strings_only=True)

        if getattr(field, "child", None):
            field_info["child"] = self.get_field_info(field.child)
        elif getattr(field, "fields", None):
            field_info["children"] = self.get_serializer_info(field)

        elif isinstance(field, serializers.ChoiceField):
            self.set_choices_field(field, field_info)

        if field.field_name == 'id':
            field_info['label'] = 'ID'

        return field_info

    @staticmethod
    def get_filters_fields(request: Any, view: Any) -> list:
        """获取视图支持的过滤字段列表。

        Args:
            request: DRF 请求对象。
            view: 视图实例。

        Returns:
            过滤字段名列表。
        """
        fields = []
        if hasattr(view, "get_filter_fields"):
            fields = view.get_filter_fields(request)
        elif hasattr(view, "filter_fields"):
            fields = view.filter_fields
        elif hasattr(view, "filterset_fields"):
            fields = view.filterset_fields
        elif hasattr(view, "get_filterset_fields"):
            fields = view.get_filterset_fields(request)
        elif hasattr(view, "filterset_class"):
            fields = list(view.filterset_class.Meta.fields) + list(
                view.filterset_class.declared_filters.keys()
            )

        if hasattr(view, "custom_filter_fields"):
            # 不能写 fields += view.custom_filter_fields
            # 会改变 view 的 filter_fields
            fields = list(fields) + list(view.custom_filter_fields)

        if isinstance(fields, dict):
            fields = list(fields.keys())
        return fields

    @staticmethod
    def get_ordering_fields(request: Any, view: Any) -> list:
        """获取视图支持的排序字段列表。

        Args:
            request: DRF 请求对象。
            view: 视图实例。

        Returns:
            排序字段名列表。
        """
        fields = []
        if hasattr(view, "get_ordering_fields"):
            fields = view.get_ordering_fields(request)
        elif hasattr(view, "ordering_fields"):
            fields = view.ordering_fields
        return fields

    def determine_metadata(self, request: Any, view: Any) -> dict:
        """生成包含过滤与排序标记的完整元数据。

        Args:
            request: DRF 请求对象。
            view: 视图实例。

        Returns:
            包含 actions、过滤与排序信息的元数据字典。
        """
        metadata = super(SimpleMetadataWithFilters, self).determine_metadata(
            request, view
        )
        filterset_fields = self.get_filters_fields(request, view)
        order_fields = self.get_ordering_fields(request, view)

        meta_get = metadata.get("actions", {}).get("GET", {})
        for k, v in meta_get.items():
            if k in filterset_fields:
                v["filter"] = True
            if k in order_fields:
                v["order"] = True
        return metadata
