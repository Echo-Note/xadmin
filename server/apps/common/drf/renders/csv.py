# ~*~ coding: utf-8 ~*~
#
"""CSV 文件渲染器模块，实现 CSV 格式导出文件的渲染与 CSV 注入转义。"""


import codecs

import unicodecsv
from six import BytesIO

from .base import BaseFileRenderer
from ..const import CSV_FILE_ESCAPE_CHARS


class CSVFileRenderer(BaseFileRenderer):
    """CSV 文件渲染器，将数据渲染为带 UTF-8 BOM 的 CSV 字节内容。"""

    media_type = 'text/csv'
    format = 'csv'
    writer = None
    buffer = None

    escape_chars = tuple(CSV_FILE_ESCAPE_CHARS)

    def initial_writer(self) -> None:
        """初始化 CSV 写入器与字节缓冲区，写入 UTF-8 BOM。"""
        csv_buffer = BytesIO()
        csv_buffer.write(codecs.BOM_UTF8)
        csv_writer = unicodecsv.writer(csv_buffer, encoding='utf-8')
        self.buffer = csv_buffer
        self.writer = csv_writer

    def __render_row(self, row: list) -> list:
        row_escape = []
        for d in row:
            if isinstance(d, str) and d.strip().startswith(self.escape_chars):
                d = "'{}".format(d)
            row_escape.append(d)
        return row_escape

    def write_row(self, row: list) -> None:
        """写入单行数据，自动处理 CSV 注入转义。

        Args:
            row: 行数据列表。
        """
        row = self.__render_row(row)
        self.writer.writerow(row)

    def get_rendered_value(self) -> bytes:
        """获取渲染后的 CSV 字节内容。

        Returns:
            CSV 文件字节内容。
        """
        value = self.buffer.getvalue()
        return value
