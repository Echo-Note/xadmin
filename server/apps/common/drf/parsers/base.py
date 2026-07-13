"""DRF 文件解析器基类模块，提供 CSV/Excel 文件导入解析的通用抽象实现。"""


import abc
import codecs
import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework import status
from rest_framework.exceptions import ParseError, APIException
from rest_framework.parsers import BaseParser

from apps.common.core.fields import LabeledChoiceField, BasePrimaryKeyRelatedField
from apps.common.utils import get_logger

logger = get_logger(__name__)


class FileContentOverflowedError(APIException):
    """文件内容超出最大长度限制时抛出的异常。"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'file_content_overflowed'
    default_detail = _('The file content overflowed (The maximum length `{}` bytes)')


class BaseFileParser(BaseParser):
    """文件解析器基类，定义 CSV/Excel 等文件导入解析的通用流程。"""

    FILE_CONTENT_MAX_LENGTH = 1024 * 1024 * 10

    serializer_cls = None
    serializer_fields = None
    obj_pattern = re.compile(r'^(.+)\(([a-z0-9-]+)\)$')

    def check_content_length(self, meta: dict) -> None:
        """检查请求内容长度是否超出限制，超出时抛出异常。

        Args:
            meta: 请求 META 字典。
        """
        content_length = int(meta.get('CONTENT_LENGTH', meta.get('HTTP_CONTENT_LENGTH', 0)))
        if content_length > self.FILE_CONTENT_MAX_LENGTH:
            msg = FileContentOverflowedError.default_detail.format(self.FILE_CONTENT_MAX_LENGTH)
            logger.error(msg)
            raise FileContentOverflowedError(msg)

    @staticmethod
    def get_stream_data(stream: Any) -> bytes:
        """读取输入流并去除 UTF-8 BOM 头。

        Args:
            stream: 可读的文件流对象。

        Returns:
            去除 BOM 后的字节数据。
        """
        stream_data = stream.read()
        stream_data = stream_data.strip(codecs.BOM_UTF8)
        return stream_data

    @abc.abstractmethod
    def generate_rows(self, stream_data: bytes) -> Iterator[list]:
        """从原始字节数据生成行迭代器，由子类实现具体逻辑。

        Args:
            stream_data: 原始字节数据。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def get_column_titles(self, rows: Iterator[list]) -> list:
        """从行迭代器中获取首行作为列标题。

        Args:
            rows: 行迭代器。

        Returns:
            列标题列表。
        """
        return next(rows)

    def convert_to_field_names(self, column_titles: list) -> list:
        """将列标题转换为序列化器字段名。

        Args:
            column_titles: 原始列标题列表。

        Returns:
            与列标题对应的字段名列表。
        """
        fields_map = {}
        fields = self.serializer_fields
        for k, v in fields.items():
            # id 是只读的, 导入更新资产平台会失败
            if v.read_only and k not in ['id', 'pk']:
                continue
            fields_map.update({
                v.label: k,
                k: k
            })
        lowercase_fields_map = {k.lower(): v for k, v in fields_map.items()}
        field_names = []
        for column_title in column_titles:
            if "(" in column_title and column_title.endswith(")"):
                field = column_title.strip('*').strip(")").split('(')[-1]
            else:
                field = lowercase_fields_map.get(column_title.strip('*').lower(), '')
            field_names.append(field)
        return field_names

    @staticmethod
    def _replace_chinese_quote(s: Any) -> Any:
        """将中文引号替换为英文引号。

        Args:
            s: 待处理的值，非字符串时原样返回。

        Returns:
            替换引号后的字符串或原值。
        """
        if not isinstance(s, str):
            return s
        trans_table = str.maketrans({
            '"': '"',
            '"': '"',
            ''': '"',
            ''': '"',
            '\'': '"'
        })
        return s.translate(trans_table)

    @classmethod
    def load_row(cls, row: list) -> list:
        """构建 JSON 数据前的行处理，转换中文引号并尝试解析 JSON 字面量。

        Args:
            row: 原始行数据列表。

        Returns:
            处理后的行数据列表。
        """
        new_row = []
        for col in row:
            # 转换中文引号
            col = cls._replace_chinese_quote(col)
            # 列表/字典转换
            if isinstance(col, str) and (
                    (col.startswith('[') and col.endswith(']')) or
                    (col.startswith("{") and col.endswith("}"))
            ):
                try:
                    col = json.loads(col)
                except json.JSONDecodeError as e:
                    logger.error('Json load error: ', e)
                    logger.error('col: ', col)
            new_row.append(col)
        return new_row

    def id_name_to_obj(self, v: Any) -> Any:
        """将 ``名称(id)`` 格式的字符串转换为包含 ``pk`` 和 ``name`` 的字典。

        Args:
            v: 待转换的值。

        Returns:
            转换后的字典；若不匹配则原样返回。
        """
        if not v or not isinstance(v, str):
            return v
        matched = self.obj_pattern.match(v)
        if not matched:
            return v
        obj_name, obj_id = matched.groups()
        if obj_id.isdigit():
            obj_id = int(obj_id)
        return {'pk': obj_id, 'name': obj_name}

    def parse_value(self, field: Any, value: Any) -> Any:
        """根据序列化器字段类型将原始值转换为目标值。

        Args:
            field: 序列化器字段实例。
            value: 原始值。

        Returns:
            转换后的值。
        """
        if value == '-' and field and field.allow_null:
            return None
        elif hasattr(field, 'to_file_internal_value'):
            value = field.to_file_internal_value(value)
        elif isinstance(field, serializers.BooleanField):
            value = value.lower() in ['true', '1', 'yes']
        elif isinstance(field, serializers.ChoiceField):
            value = value
        elif isinstance(field, BasePrimaryKeyRelatedField):
            if field.many:
                value = [self.id_name_to_obj(v) for v in value]
            else:
                value = self.id_name_to_obj(value)
        elif isinstance(field, LabeledChoiceField):
            value = self.id_name_to_obj(value)
            if isinstance(value, dict) and 'pk' in value:
                value = value.get('pk')
        elif isinstance(field, serializers.ListSerializer):
            value = [self.parse_value(field.child, v) for v in value]
        elif isinstance(field, serializers.Serializer):
            value = self.id_name_to_obj(value)
        elif isinstance(field, serializers.ManyRelatedField):
            value = [self.parse_value(field.child_relation, v) for v in value]
        elif isinstance(field, serializers.ListField):
            value = [self.parse_value(field.child, v) for v in value]
        elif isinstance(field, serializers.JSONField):
            if isinstance(value, str):
                if value.lower() in ['yes']:
                    return True
                elif value.lower() in ['no']:
                    return False
            try:
                value = json.loads(value)
            except:
                pass
        elif isinstance(field, serializers.CharField):
            if not isinstance(value, str):
                value = json.dumps(value)
        elif isinstance(field, serializers.FileField):
            value = None

        return value

    def process_row_data(self, row_data: dict) -> dict:
        """构建 JSON 数据后的行数据处理，根据字段类型解析每个值。

        Args:
            row_data: 键值对形式的行数据。

        Returns:
            处理后的行数据字典。
        """
        new_row = {}
        for k, v in row_data.items():
            field = self.serializer_fields.get(k)
            v = self.parse_value(field, v)
            new_row[k] = v
        return new_row

    def generate_data(self, fields_name: list, rows: Iterable[list]) -> list:
        """根据字段名和行数据生成最终的字典列表。

        Args:
            fields_name: 字段名列表。
            rows: 行数据可迭代对象。

        Returns:
            处理后的数据字典列表。
        """
        data = []
        for row in rows:
            # 空行不处理
            if not any(row):
                continue
            row = self.load_row(row)
            row_data = dict(zip(fields_name, row))
            row_data = self.process_row_data(row_data)
            data.append(row_data)
        return data

    @staticmethod
    def pop_help_text_if_need(rows: Iterable[list]) -> list:
        """如果首行以 ``#Help`` 开头则移除帮助行。

        Args:
            rows: 行数据可迭代对象。

        Returns:
            处理后的行列表。
        """
        rows = list(rows)
        if not rows:
            return rows
        if rows[0][0].startswith('#Help'):
            rows.pop(0)
        return rows

    def parse(self, stream: Any, media_type: str | None = None, parser_context: dict | None = None) -> list:
        """解析输入流，返回转换后的数据字典列表。

        Args:
            stream: 输入流对象。
            media_type: 媒体类型，可选。
            parser_context: 解析上下文字典。

        Returns:
            解析后的数据字典列表。

        Raises:
            ParseError: 解析过程中发生错误时抛出。
        """
        assert parser_context is not None, '`parser_context` should not be `None`'

        view = parser_context['view']
        request = view.request

        try:
            meta = request.META
            self.serializer_cls = view.get_serializer_class()
            self.serializer_fields = self.serializer_cls().fields
        except Exception as e:
            logger.debug(e, exc_info=True)
            raise ParseError(_("The resource does not support imports!"))

        self.check_content_length(meta)
        try:
            stream_data = self.get_stream_data(stream)
            rows = self.generate_rows(stream_data)
            column_titles = self.get_column_titles(rows)
            field_names = self.convert_to_field_names(column_titles)

            # 给 `common.mixins.api.RenderToJsonMixin` 提供，暂时只能耦合
            column_title_field_pairs = list(zip(column_titles, field_names))
            column_title_field_pairs = [(k, v) for k, v in column_title_field_pairs if k and v]
            if not hasattr(request, 'jms_context'):
                request.jms_context = {}
            request.jms_context['column_title_field_pairs'] = column_title_field_pairs

            rows = self.pop_help_text_if_need(rows)
            data = self.generate_data(field_names, rows)
            return data
        except Exception as e:
            logger.error(e, exc_info=True)
            raise ParseError(_("Parse file error: {}").format(str(e)))
