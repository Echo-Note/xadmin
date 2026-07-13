# ~*~ coding: utf-8 ~*~
#
"""CSV 文件解析器模块，实现 CSV 格式导入文件的解析与转义处理。"""


from functools import cached_property
from collections.abc import Iterator

import chardet
import unicodecsv

from .base import BaseFileParser
from ..const import CSV_FILE_ESCAPE_CHARS


class CSVFileParser(BaseFileParser):
    """CSV 文件解析器，支持自动检测编码并处理 CSV 注入转义。"""

    media_type = 'text/csv'

    @cached_property
    def match_escape_chars(self) -> tuple:
        """生成需要转义的前缀字符元组（含单双引号前缀）。"""
        chars = []
        for c in CSV_FILE_ESCAPE_CHARS:
            dq_char = '"{}'.format(c)
            sg_char = "'{}".format(c)
            chars.append(dq_char)
            chars.append(sg_char)
        return tuple(chars)

    @staticmethod
    def _universal_newlines(stream: bytes) -> Iterator[bytes]:
        """保证在通用换行模式下逐行产出数据。

        Args:
            stream: 原始字节数据。

        Yields:
            每一行的字节数据。
        """
        for line in stream.splitlines():
            yield line

    def __parse_row(self, row: list) -> list:
        row_escape = []
        for d in row:
            if isinstance(d, str) and d.strip().startswith(self.match_escape_chars):
                d = d.lstrip("'").lstrip('"')
            row_escape.append(d)
        return row_escape

    def generate_rows(self, stream_data: bytes) -> Iterator[list]:
        """解析 CSV 字节数据，逐行产出转义后的行列表。

        Args:
            stream_data: 原始 CSV 字节数据。

        Yields:
            转义后的每一行数据列表。
        """
        detect_result = chardet.detect(stream_data)
        encoding = detect_result.get("encoding", "utf-8")
        lines = self._universal_newlines(stream_data)
        csv_reader = unicodecsv.reader(lines, encoding=encoding)
        for row in csv_reader:
            row = self.__parse_row(row)
            yield row
