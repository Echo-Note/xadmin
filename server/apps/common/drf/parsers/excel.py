"""Excel 文件解析器模块，实现 xlsx 格式导入文件的解析。"""


from collections.abc import Iterator

import pyexcel
from django.utils.translation import gettext_lazy as _

from .base import BaseFileParser


class ExcelFileParser(BaseFileParser):
    """Excel (xlsx) 文件解析器，通过 pyexcel 读取工作表行数据。"""

    media_type = 'text/xlsx'

    def generate_rows(self, stream_data: bytes) -> Iterator[list]:
        """解析 Excel 字节数据，返回行迭代器。

        Args:
            stream_data: 原始 Excel 字节数据。

        Returns:
            工作表行数据迭代器。

        Raises:
            Exception: Excel 文件无效时抛出。
        """
        try:
            workbook = pyexcel.get_book(file_type='xlsx', file_content=stream_data)
        except Exception as e:
            raise Exception(_('Invalid excel file {}').format(str(e)))
        # 默认获取第一个工作表sheet
        sheet = workbook.sheet_by_index(0)
        rows = sheet.rows()
        return rows
