"""DRF 文件渲染器包，提供 CSV、Excel 透传等文件导出渲染器。"""


from typing import Any

from rest_framework import renderers

from .csv import *
from .excel import *


class PassthroughRenderer(renderers.BaseRenderer):
    """透传渲染器，直接返回原始数据，由视图提供 Response。"""

    media_type = 'application/octet-stream'
    format = ''

    def render(self, data: Any, accepted_media_type: str | None = None, renderer_context: dict | None = None) -> Any:
        """渲染数据，直接原样返回。

        Args:
            data: 原始数据。
            accepted_media_type: 接受的媒体类型，可选。
            renderer_context: 渲染上下文，可选。

        Returns:
            原始数据。
        """
        return data
