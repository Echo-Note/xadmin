#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : fields
# author : ly_13
# date : 8/6/2024
"""自定义序列化器字段模块，提供标签选择字段、主键关联字段、手机号字段等。"""
from functools import partial
from typing import Any

import phonenumbers
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, QuerySet
from django.db.models.fields.files import FieldFile
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.request import Request

from apps.common.core.filter import get_filter_queryset
from apps.common.fields.utils import get_file_absolute_uri
from server.utils import get_current_request


def attr_get(obj: Any, attr: str, sp: str = '.') -> Any:
    """通过分隔符拆分属性路径，递归获取对象的嵌套属性值。

    Args:
        obj: 目标对象。
        attr: 属性路径字符串，以 ``sp`` 分隔。
        sp: 属性路径分隔符。

    Returns:
        最终获取到的属性值。
    """
    names = attr.split(sp)

    def func(o: Any) -> Any:
        for name in names:
            o = getattr(o, name)
        return o

    return func(obj)


class LabeledChoiceField(serializers.ChoiceField):
    """带标签的 choice 字段，序列化时返回 value+label 结构。"""

    def __init__(self, **kwargs: Any) -> None:
        """初始化标签选择字段。

        Args:
            **kwargs: 透传给父类的关键字参数，支持 ``attrs`` 自定义返回字段。
        """
        self.attrs = kwargs.pop("attrs", None) or ("value", "label")
        super().__init__(**kwargs)

    def to_representation(self, key: Any) -> dict | None:
        """将 choice 值序列化为 value+label 字典。

        Args:
            key: choice 的原始值。

        Returns:
            包含 value 和 label 的字典，值为 None 时原样返回。
        """
        if key is None:
            return key
        label = self.choices.get(key, key)
        return {"value": key, "label": label}

    def to_internal_value(self, data: Any) -> Any:
        """将前端传入的数据转换为内部 choice 值。

        支持字典、带括号字符串等多种输入格式。

        Args:
            data: 前端传入的数据。

        Returns:
            转换后的内部值。
        """
        if not data:
            return data
        if isinstance(data, dict):
            data = data.get("value")
        if isinstance(data, str) and "(" in data and data.endswith(")"):
            data = data.strip(")").split('(')[-1]
        return super(LabeledChoiceField, self).to_internal_value(data)

    def get_schema(self) -> dict:
        """为 drf-spectacular 提供 OpenAPI schema"""
        if getattr(self, 'many', False):
            return {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'value': {'type': 'string'},
                        'label': {'type': 'string'}
                    }
                },
                'description': getattr(self, 'help_text', ''),
                'title': getattr(self, 'label', ''),
            }
        else:
            return {
                'type': 'object',
                'properties': {
                    'value': {'type': 'string'},
                    'label': {'type': 'string'}
                },
                'description': getattr(self, 'help_text', ''),
                'title': getattr(self, 'label', ''),
            }


class LabeledMultipleChoiceField(serializers.MultipleChoiceField):
    """带标签的多选 choice 字段，序列化时返回 value+label 列表。"""

    def __init__(self, **kwargs: Any) -> None:
        """初始化多选标签字段，构建 choice 映射表。

        Args:
            **kwargs: 透传给父类的关键字参数。
        """
        super().__init__(**kwargs)
        self.choice_mapper = {
            key: value for key, value in self.choices.items()
        }

    def to_representation(self, keys: list | None) -> list | None:
        """将 choice 值列表序列化为 value+label 字典列表。

        Args:
            keys: choice 原始值列表。

        Returns:
            包含 value 和 label 的字典列表，值为 None 时原样返回。
        """
        if keys is None:
            return keys
        return [
            {"value": key, "label": self.choice_mapper.get(key)}
            for key in keys
        ]

    def to_internal_value(self, data: list) -> list:
        """将前端传入的数据列表转换为内部 choice 值列表。

        Args:
            data: 前端传入的数据列表。

        Returns:
            转换后的内部值列表。
        """
        if not data:
            return data

        if isinstance(data[0], dict):
            return [item.get("value") for item in data]
        else:
            return data


class BasePrimaryKeyRelatedField(serializers.RelatedField):
    """
    Base class for primary key related fields.
    """
    default_error_messages = {
        "required": _("This field is required."),
        "does_not_exist": _('Invalid pk "{pk_value}" - object does not exist.'),
        "incorrect_type": _("Incorrect type. Expected pk value, received {data_type}."),
        "queryset_none": _("The query set is empty."),
    }

    def __init__(self, attrs: list | None = None, ignore_field_permission: bool = False, **kwargs: Any) -> None:
        """
        :param attrs: 默认为 None，返回默认的 pk， 一般需要自定义
        :param ignore_field_permission: 忽略字段权限控制
        """
        self.attrs = attrs if attrs else ["pk"]
        self.label_format = kwargs.pop("format", None)
        self.input_type = kwargs.pop("input_type", None)
        self.input_type_prefix = kwargs.pop("input_type_prefix", None)
        self.input_type_suffix = kwargs.pop("input_type_suffix", None)
        self.many = kwargs.get("many", False)
        super().__init__(**kwargs)
        self.request: Request = get_current_request()
        self.ignore_field_permission = ignore_field_permission

    def use_pk_only_optimization(self) -> bool:
        """是否使用 pk_only 优化，本字段始终返回 False。"""
        return False

    def __add_request(self) -> None:
        """延迟补充 request 对象，确保后续可用。"""
        if not self.request:
            self.request = get_current_request()

    def get_queryset(self) -> QuerySet | None:
        """获取查询集，并根据当前用户进行数据权限过滤。

        Returns:
            过滤后的查询集，用户未认证时返回原始查询集。
        """
        self.__add_request()
        if self.request and self.request.user and self.request.user.is_authenticated:
            return get_filter_queryset(super().get_queryset(), self.request.user)
        return super().get_queryset()

    def display_value(self, instance: Model) -> str:
        """用于自定义的choices中value的展示，默认是 str(instance) ，可以通过在model中重写__str__方法，也可以在此方法定义"""
        return super().display_value(instance)

    def get_choices(self, cutoff: int | None = None) -> list | dict:
        """用于获取可选"""
        is_column = getattr(self, 'is_column', False)
        queryset = self.get_queryset()
        if queryset is None:
            # Ensure that field.choices returns something sensible
            # even when accessed with a read-only field.
            return [] if is_column else {}

        if cutoff is not None:
            queryset = queryset[:cutoff]

        if is_column:
            result = []
            for item in queryset:
                data = self.to_representation(item)
                if isinstance(data, dict):
                    if "pk" in data:
                        data['value'] = data.get("pk")
                else:
                    data = {"value": data, "label": data}
                result.append(data)
        else:
            result = {}
            for item in queryset:
                key = self.to_representation(item)
                if isinstance(key, dict):
                    key = key.get("pk")
                result[key] = self.display_value(item)
        return result

    def get_allow_fields(self, value: Model) -> set:
        """根据字段权限获取允许返回的字段集合。

        Args:
            value: 模型实例对象。

        Returns:
            允许返回的字段名集合。
        """
        self.__add_request()
        if self.attrs is None:  # 默认没写attrs, 返回默认pk
            return self.attrs
        fields = [x.name for x in value._meta.fields]

        if not isinstance(self.attrs, (list, set)):  # 如果存在，且不是列表，则返回所有字段
            self.attrs = fields
        extra_fields = set(self.attrs) - set(fields)  # 这些字段不在model内，并且不受权限控制

        if self.ignore_field_permission or (self.request and hasattr(self.request, "ignore_field_permission")):
            return set(self.attrs)

        allow_fields = []
        if self.request and settings.PERMISSION_FIELD_ENABLED:
            if hasattr(self.request, "user") and self.request.user and self.request.user.is_superuser:
                allow_fields = self.attrs
            elif hasattr(self.request, "fields"):
                if self.request.fields and isinstance(self.request.fields, dict):
                    allow_fields = self.request.fields.get(value._meta.label_lower, [])
        else:
            allow_fields = self.attrs

        return set(self.attrs) & set(allow_fields) | extra_fields

    def to_representation(self, value: Model) -> Any:
        """将模型实例序列化为字典表示。

        Args:
            value: 模型实例对象。

        Returns:
            包含允许字段的字典，无允许字段时返回主键值。
        """
        attrs = self.get_allow_fields(value)
        if not attrs:
            return value.pk
        data = {}
        for attr in attrs:
            # if not hasattr(value, attr):
            #     continue
            # data[attr] = getattr(value, attr)
            try:
                data[attr] = attr_get(value, attr, '__')
            except:
                continue
            if isinstance(data[attr], FieldFile):
                data[attr] = get_file_absolute_uri(data[attr], self.request)
            if isinstance(data[attr], partial):
                data[attr] = data[attr]()
        if data:
            if self.label_format:
                try:
                    data["label"] = self.label_format.format(**data)
                except Exception:  # 使用权限控制的时候，format字段可能不在权限里面
                    data["label"] = data.get("pk")
            else:
                if "label" not in self.attrs:
                    data["label"] = data.get("pk")
        return data

    def to_internal_value(self, data: Any) -> Model:
        """将前端数据转换为模型实例。

        Args:
            data: 前端传入的数据，可为模型实例、字典或主键值。

        Returns:
            查询到的模型实例。

        Raises:
            ValidationError: 数据不存在或类型不正确时抛出。
        """
        queryset = self.get_queryset()
        if queryset is None:
            return self.fail("queryset_none")
        if isinstance(data, Model):
            return queryset.get(pk=data.pk)

        if not isinstance(data, dict):
            pk = data
        else:
            pk = data.get("id") or data.get("pk") or data.get(self.attrs[0])

        try:
            if isinstance(data, bool):
                raise TypeError
            return queryset.get(pk=pk)
        except ObjectDoesNotExist:
            self.fail("does_not_exist", pk_value=pk)
        except (TypeError, ValueError):
            self.fail("incorrect_type", data_type=type(pk).__name__)

    def get_schema(self) -> dict:
        """为 drf-spectacular 提供 OpenAPI schema"""
        # 获取字段的基本信息
        field_type = 'array' if self.many else 'object'

        if field_type == 'array':
            # 如果是多对多关系
            return {
                'type': 'array',
                'items': self._get_openapi_item_schema(),
                'description': getattr(self, 'help_text', ''),
                'title': getattr(self, 'label', ''),
            }
        else:
            # 如果是一对一关系
            return {
                'type': 'object',
                'properties': self._get_openapi_properties_schema(),
                'description': getattr(self, 'help_text', ''),
                'title': getattr(self, 'label', ''),
            }

    def _get_openapi_item_schema(self) -> dict:
        """获取数组项的 OpenAPI schema"""
        return self._get_openapi_object_schema()

    def _get_openapi_object_schema(self) -> dict:
        """获取对象的 OpenAPI schema"""
        properties = {}

        # 动态分析 attrs 中的属性类型
        for attr in self.attrs:
            # 尝试从 queryset 的 model 中获取字段信息
            field_type = self._infer_field_type(attr)
            properties[attr] = {
                'type': field_type,
                'description': f'{attr} field'
            }

        return {
            'type': 'object',
            'properties': properties,
            'required': ['id'] if 'id' in self.attrs else []
        }

    def _infer_field_type(self, attr_name: str) -> str:
        """智能推断字段类型"""
        try:
            # 如果有 queryset，尝试从 model 中获取字段信息
            if hasattr(self, 'queryset') and self.queryset is not None:
                model = self.queryset.model
                if hasattr(model, '_meta') and hasattr(model._meta, 'fields'):
                    field = model._meta.get_field(attr_name)
                    if field:
                        return self._map_django_field_type(field)
        except Exception:
            pass

        # 如果没有 queryset 或无法获取字段信息，使用启发式规则
        return self._heuristic_field_type(attr_name)

    def _map_django_field_type(self, field: Any) -> str:
        """将 Django 字段类型映射到 OpenAPI 类型

        Args:
            field: Django 模型字段对象。

        Returns:
            OpenAPI 类型字符串。
        """
        field_type = type(field).__name__

        # 整数类型
        if 'Integer' in field_type or 'BigInteger' in field_type or 'SmallInteger' in field_type:
            return 'integer'
        # 浮点数类型
        elif 'Float' in field_type or 'Decimal' in field_type:
            return 'number'
        # 布尔类型
        elif 'Boolean' in field_type:
            return 'boolean'
        # 日期时间类型
        elif 'DateTime' in field_type or 'Date' in field_type or 'Time' in field_type:
            return 'string'
        # 文件类型
        elif 'File' in field_type or 'Image' in field_type:
            return 'string'
        # 其他类型默认为字符串
        else:
            return 'string'

    def _heuristic_field_type(self, attr_name: str) -> str:
        """启发式推断字段类型

        Args:
            attr_name: 属性名。

        Returns:
            OpenAPI 类型字符串。
        """
        # 基于属性名的启发式规则

        if attr_name in ['is_active', 'enabled', 'visible'] or attr_name.startswith('is_'):
            return 'boolean'
        elif attr_name in ['count', 'number', 'size', 'amount']:
            return 'integer'
        elif attr_name in ['price', 'rate', 'percentage']:
            return 'number'
        else:
            # 默认返回字符串类型
            return 'string'

    def _get_openapi_properties_schema(self) -> dict:
        """获取对象属性的 OpenAPI schema"""
        return self._get_openapi_object_schema()['properties']


class PhoneField(serializers.CharField):
    """手机号字段，支持带区号的输入输出格式。"""

    def __init__(self, **kwargs: Any) -> None:
        """初始化手机号字段，设置 input_type 为 phone。

        Args:
            **kwargs: 透传给父类的关键字参数。
        """
        self.input_type = 'phone'
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> str:
        """将前端传入的手机号数据转换为标准格式。

        支持字典格式（code+phone）和纯字符串格式。

        Args:
            data: 前端传入的手机号数据。

        Returns:
            标准化后的手机号字符串。
        """
        if isinstance(data, dict):
            code = data.get('code')
            phone = data.get('phone', '')
            if code and phone:
                code = code.replace('+', '')
                data = '+{}{}'.format(code, phone)
            else:
                data = phone
        if data:
            try:
                phone = phonenumbers.parse(data, 'CN')
                data = '+{}{}'.format(phone.country_code, phone.national_number)
            except phonenumbers.NumberParseException:
                data = '+86{}'.format(data)

        return super().to_internal_value(data)

    def to_representation(self, value: str) -> dict:
        """将手机号字符串序列化为带区号的字典格式。

        Args:
            value: 手机号字符串。

        Returns:
            包含 code 和 phone 的字典。
        """
        try:
            phone = phonenumbers.parse(value, 'CN')
            value = {'code': '+%s' % phone.country_code, 'phone': phone.national_number}
        except phonenumbers.NumberParseException:
            value = {'code': '+86', 'phone': value}
        return value


class ColorField(serializers.CharField):
    """颜色选择字段，前端以颜色选择器展示。"""

    def __init__(self, **kwargs: Any) -> None:
        """初始化颜色字段，设置 input_type 为 color。

        Args:
            **kwargs: 透传给父类的关键字参数。
        """
        self.input_type = 'color'
        super().__init__(**kwargs)
