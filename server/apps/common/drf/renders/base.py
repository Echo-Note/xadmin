"""DRF 文件渲染器基类模块，提供 CSV/Excel 文件导出渲染的通用抽象实现。"""


import abc
import io
import re
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

import pyzipper
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.renderers import BaseRenderer
from rest_framework.utils import encoders, json

from apps.common.core.fields import LabeledChoiceField, BasePrimaryKeyRelatedField, PhoneField
from apps.common.core.utils import has_self_fields
from apps.common.utils import get_logger
from apps.common.utils.timezone import local_now

logger = get_logger(__name__)


class BaseFileRenderer(BaseRenderer):
    """文件渲染器基类，定义 CSV/Excel 等文件导出渲染的通用流程。"""

    # 渲染模板标识, 导入、导出、更新模板: ['import', 'update', 'export']
    template = 'export'
    serializer = None

    @staticmethod
    def _check_validation_data(data: dict) -> bool:
        """检查响应数据是否为校验错误数据。

        Args:
            data: 响应数据字典。

        Returns:
            若包含 ``detail`` 键则返回 False，否则返回 True。
        """
        detail_key = "detail"
        if detail_key in data:
            return False
        return True

    @staticmethod
    def _json_format_response(response_data: Any) -> str:
        """将响应数据序列化为 JSON 字符串。

        Args:
            response_data: 待序列化的数据。

        Returns:
            JSON 字符串。
        """
        return json.dumps(response_data)

    def set_response_disposition(self, response: Any) -> None:
        """根据序列化器模型和模板类型设置响应的 Content-Disposition 头。

        Args:
            response: HTTP 响应对象。
        """
        serializer = self.serializer
        if response and hasattr(serializer, 'Meta') and hasattr(serializer.Meta, "model"):
            filename_prefix = serializer.Meta.model.__name__.lower()
        else:
            filename_prefix = 'download'
        suffix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if self.template == 'import':
            suffix = 'template'
        filename = "{}_{}.{}".format(filename_prefix, suffix, self.format)
        disposition = 'attachment; filename="{}"'.format(filename)
        response['Content-Disposition'] = disposition
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'

    def get_rendered_fields(self) -> list:
        """根据模板类型获取需要渲染的序列化器字段列表。

        Returns:
            序列化器字段实例列表。
        """
        fields = self.serializer.fields
        meta = getattr(self.serializer, 'Meta', None)
        pk_field = fields.get('pk')
        if self.template == 'import':
            fields = [v for k, v in fields.items() if not v.read_only and k not in ['id', 'pk']]
            fields_unimport = getattr(meta, 'fields_unimport', [])
            fields = [v for v in fields if v.field_name not in fields_unimport]
            # 当模型存在自关联字段时，import 模板需要包含 pk 字段用于拓扑排序
            if pk_field and meta and hasattr(meta, 'model'):
                field_names = [f.field_name for f in fields]
                if has_self_fields(meta.model, field_names):
                    fields.insert(0, pk_field)
        elif self.template == 'update':
            fields = [v for k, v in fields.items() if not v.read_only]
            if pk_field:
                fields.insert(0, pk_field)
        else:
            fields = [v for k, v in fields.items() if not v.write_only and k not in ['id', 'pk']]
            if pk_field:
                fields.insert(0, pk_field)

        fields_unexport = getattr(meta, 'fields_unexport', [])
        fields = [v for v in fields if v.field_name not in fields_unexport]
        return fields

    @staticmethod
    def get_column_titles(render_fields: list) -> list:
        """根据渲染字段生成列标题列表。

        Args:
            render_fields: 渲染字段实例列表。

        Returns:
            列标题字符串列表。
        """
        titles = []
        for field in render_fields:
            name = field.label
            if field.required:
                name = '*' + name
            titles.append(f"{name}({field.field_name})")
        return titles

    def process_data(self, data: dict) -> list:
        """处理原始数据，根据模板类型筛选并序列化为 JSON 兼容的列表。

        Args:
            data: 原始数据字典或列表。

        Returns:
            处理后的数据列表。
        """
        results = data['results'] if 'results' in data else data

        if isinstance(results, dict):
            results = [results]

        if self.template == 'import':
            results = [results[0]] if results else results
        else:
            # 限制数据数量
            results = results[:settings.EXPORT_MAX_LIMIT]
        # 会将一些 UUID 字段转化为 string
        results = json.loads(json.dumps(results, cls=encoders.JSONEncoder))
        return results

    @staticmethod
    def to_id_name(value: dict | None) -> str:
        """将对象字典转换为 ``名称(id)`` 格式的字符串。

        Args:
            value: 包含 id/pk/name 等键的字典，可为 None。

        Returns:
            格式化后的字符串，value 为 None 时返回 ``-``。
        """
        if value is None:
            return '-'
        pk = str(value.get('id', '') or value.get('pk', ''))
        name = value.get('display_name', '') or value.get('name', '') or value.get('username', '') or value.get(
            'nickname', '') or pk
        return '{}({})'.format(name, pk)

    @staticmethod
    def to_choice_name(value: dict | None) -> str:
        """从选项字典中提取 ``value`` 字段。

        Args:
            value: 选项字典，可为 None。

        Returns:
            选项值字符串，value 为 None 时返回 ``-``。
        """
        if value is None:
            return '-'
        value = value.get('value', '')
        return value

    def render_value(self, field: Any, value: Any) -> str:
        """根据序列化器字段类型将原始值渲染为字符串。

        Args:
            field: 序列化器字段实例。
            value: 原始值。

        Returns:
            渲染后的字符串。
        """
        if value is None:
            value = '-'
        elif hasattr(field, 'to_file_representation'):
            value = field.to_file_representation(value)
        elif isinstance(field, serializers.BooleanField):
            value = 'Yes' if value else 'No'
        elif isinstance(field, LabeledChoiceField):
            value = value or {}
            value = '{}({})'.format(value.get('label'), value.get('value'))
        elif isinstance(field, BasePrimaryKeyRelatedField):
            if field.many:
                value = [self.to_id_name(v) for v in value]
            else:
                value = self.to_id_name(value)
        elif isinstance(field, serializers.ListSerializer):
            value = [self.render_value(field.child, v) for v in value]
        elif isinstance(field, serializers.Serializer) and value.get('id'):
            value = self.to_id_name(value)
        elif isinstance(field, serializers.ManyRelatedField):
            value = [self.render_value(field.child_relation, v) for v in value]
        elif isinstance(field, serializers.ListField):
            value = [self.render_value(field.child, v) for v in value]
        elif isinstance(field, serializers.JSONField):
            value = json.dumps(value)

        if not isinstance(value, str):
            value = json.dumps(value, cls=encoders.JSONEncoder, ensure_ascii=False)
        return str(value)

    def get_field_help_text(self, field: Any) -> str:
        """根据序列化器字段类型生成帮助文本。

        Args:
            field: 序列化器字段实例。

        Returns:
            帮助文本字符串。
        """
        text = ''
        if hasattr(field, 'get_render_help_text'):
            text = field.get_render_help_text()
        elif isinstance(field, serializers.BooleanField):
            text = _('Yes/No')
        elif isinstance(field, serializers.CharField):
            if field.max_length:
                text = _('Text, max length {}').format(field.max_length)
            else:
                text = _("Long text, no length limit")
        elif isinstance(field, serializers.IntegerField):
            text = _('Number, min {}, max {}').format(field.min_value, field.max_value)
        elif isinstance(field, serializers.FloatField):
            text = _('Float, min {}, max {}').format(field.min_value, field.max_value)
        elif isinstance(field, serializers.DecimalField):
            text = _('Decimal, min {}, max {}, max_digits {}, decimal_places {}').format(field.min_value,
                                                                                         field.max_value,
                                                                                         field.max_digits,
                                                                                         field.decimal_places)
        elif isinstance(field, serializers.DateTimeField):
            text = _('Datetime format {}').format(local_now().strftime(settings.REST_FRAMEWORK['DATETIME_FORMAT']))
        elif isinstance(field, serializers.IPAddressField):
            text = _('IP')
        elif isinstance(field, serializers.ChoiceField):
            choices = [str(v) for v in field.choices.keys()]
            if isinstance(field, LabeledChoiceField):
                text = _("Choices, format name(value), name is optional for human read,"
                         " value is requisite, options {}").format(','.join(choices))
            else:
                text = _("Choices, options {}").format(",".join(choices))
        elif isinstance(field, PhoneField):
            text = _("Phone number, format +8612345678901")
        elif isinstance(field, LabeledChoiceField):
            text = _('Label, format ["key:value"]')
        elif isinstance(field, BasePrimaryKeyRelatedField):
            text = _("Object, format name(id), name is optional for human read, id is requisite")
        elif isinstance(field, serializers.PrimaryKeyRelatedField):
            text = _('Object, format id')
        elif isinstance(field, serializers.ManyRelatedField):
            child_relation_class_name = field.child_relation.__class__.__name__
            if child_relation_class_name == "ObjectRelatedField":
                text = _('Objects, format ["name(id)", ...], name is optional for human read, id is requisite')
            elif child_relation_class_name == "LabelRelatedField":
                text = _('Labels, format ["key:value", ...], if label not exists, will create it')
            else:
                text = _('Objects, format ["id", ...]')
        elif isinstance(field, serializers.ListSerializer):
            child = field.child
            if hasattr(child, 'get_render_help_text'):
                text = child.get_render_help_text()
        elif isinstance(field, serializers.JSONField):
            text = _('JSON')
        elif isinstance(field, serializers.UUIDField):
            text = _('UUID4')
        if isinstance(field, (serializers.IntegerField, serializers.FloatField, serializers.DecimalField)):
            n_text = []
            for t in text.split(','):
                if 'None' not in t:
                    n_text.append(t)
            text = ','.join(n_text)
        return text

    def generate_rows(self, data: list, render_fields: list) -> Iterator[list]:
        """根据数据与渲染字段生成行迭代器。

        Args:
            data: 数据字典列表。
            render_fields: 渲染字段实例列表。

        Yields:
            每一行的值列表。
        """
        for item in data:
            row = []
            for field in render_fields:
                value = item.get(field.field_name)
                value = self.render_value(field, value)
                row.append(value)
            yield row

    def write_help_text_if_need(self) -> None:
        """如果是导入/更新模板，则在文件开头写入帮助行。"""
        if self.template == 'export':
            return
        fields = self.get_rendered_fields()
        row = []
        for f in fields:
            text = self.get_field_help_text(f)
            row.append(text)
        row[0] = '#Help ' + str(row[0])
        self.write_row(row)

    @abc.abstractmethod
    def initial_writer(self) -> None:
        """初始化写入器，由子类实现具体逻辑。"""
        raise NotImplementedError

    def add_validation(self, rendered_fields: list) -> None:
        """为渲染字段添加数据验证（子类可覆盖）。

        Args:
            rendered_fields: 渲染字段实例列表。
        """
        pass

    def write_column_titles(self, column_titles: list) -> None:
        """写入列标题行。

        Args:
            column_titles: 列标题列表。
        """
        self.write_row(column_titles)

    def write_rows(self, rows: Iterable[list]) -> None:
        """批量写入多行数据。

        Args:
            rows: 行数据可迭代对象。
        """
        for row in rows:
            self.write_row(row)

    @abc.abstractmethod
    def write_row(self, row: list) -> None:
        """写入单行数据，由子类实现具体逻辑。

        Args:
            row: 行数据列表。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_rendered_value(self) -> bytes:
        """获取渲染后的文件内容，由子类实现具体逻辑。"""
        raise NotImplementedError

    def after_render(self) -> None:
        """渲染完成后的后处理钩子（子类可覆盖）。"""
        pass

    def render(self, data: Any, accepted_media_type: str | None = None, renderer_context: dict | None = None) -> bytes:
        """渲染数据为文件字节内容。

        Args:
            data: 待渲染的数据。
            accepted_media_type: 接受的媒体类型，可选。
            renderer_context: 渲染上下文字典，可选。

        Returns:
            渲染后的文件字节内容。
        """
        if data is None:
            return bytes()

        if not self._check_validation_data(data):
            # return self._json_format_response(data)
            data = data.get('data', {})
        try:
            renderer_context = renderer_context or {}
            request = renderer_context['request']
            response = renderer_context['response']
            view = renderer_context['view']
            self.template = request.query_params.get('template', 'export')
            self.serializer = view.get_serializer()
            self.set_response_disposition(response)
        except Exception as e:
            logger.debug(e, exc_info=True)
            value = f'The resource not support export! error:{e}'.encode('utf-8')
            return value

        try:
            rendered_fields = self.get_rendered_fields()
            column_titles = self.get_column_titles(rendered_fields)
            data = self.process_data(data)
            rows = self.generate_rows(data, rendered_fields)
            self.initial_writer()
            # self.add_validation(rendered_fields)  # 关闭校验，通过help来进行提醒
            self.write_column_titles(column_titles)
            self.write_help_text_if_need()
            self.write_rows(rows)
            self.after_render()
            value = self.get_rendered_value()
            if getattr(view, 'export_as_zip', False) and self.template == 'export':
                value = self.compress_into_zip_file(value, request, response)
        except Exception as e:
            logger.debug(e, exc_info=True)
            value = f'Render error! media:{self.media_type} \r\nerror:\r\n{e}'.encode('utf-8')
            response['Content-Disposition'] = response['Content-Disposition'].replace(self.format, 'txt')
            return value
        return value

    def compress_into_zip_file(self, value: bytes, request: Any, response: Any) -> bytes:
        """将文件内容压缩为 AES 加密的 zip 文件。

        Args:
            value: 原始文件字节内容。
            request: DRF 请求对象。
            response: HTTP 响应对象。

        Returns:
            加密压缩后的 zip 字节内容。
        """
        filename_pattern = re.compile(r'filename="([^"]+)"')
        content_disposition = response['Content-Disposition']
        match = filename_pattern.search(content_disposition)
        filename = match.group(1)
        response['Content-Disposition'] = content_disposition.replace(self.format, 'zip')

        contents_io = io.BytesIO()
        secret_key = request.user.username  # 默认密码是用户名，后期可配置
        if not secret_key:
            content = _("{} - The encryption password has not been set - "
                        "please go to personal information -> file encryption password "
                        "to set the encryption password").format(request.user.nickname)

            response['Content-Disposition'] = content_disposition.replace(self.format, 'txt')
            contents_io.write(content.encode('utf-8'))
            return contents_io.getvalue()

        with pyzipper.AESZipFile(
                contents_io, 'w', compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES
        ) as zf:
            zf.setpassword(secret_key.encode('utf8'))
            zf.writestr(filename, value)
        return contents_io.getvalue()
