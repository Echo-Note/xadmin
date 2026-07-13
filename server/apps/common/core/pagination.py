#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : pagination
# author : ly_13
# date : 6/16/2023
# -*- coding: utf-8 -*-
"""分页模块，提供基于页码的分页器及动态分页配置。"""

from collections import OrderedDict
from typing import Any

from drf_spectacular.plumbing import build_object_type, build_basic_type
from drf_spectacular.types import OpenApiTypes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class PageNumber(PageNumberPagination):
    """基于页码的分页器，支持通过 URL 参数控制每页条数。"""

    page_size = 20  # 每页显示多少条
    page_size_query_param = 'size'  # URL中每页显示条数的参数
    page_query_param = 'page'  # URL中页码的参数
    max_page_size = 100  # 返回最大数据条数

    def get_paginated_response(self, data: list) -> Response:
        """构建分页响应对象。

        Args:
            data: 当前页的数据列表。

        Returns:
            包含 total 和 results 字段的 ``Response`` 对象。
        """
        return Response(
            OrderedDict(
                [
                    ('total', self.page.paginator.count),
                    # ('next', self.get_next_link()),
                    # ('previous', self.get_previous_link()),
                    ('results', data),
                ]
            )
        )

    def get_paginated_response_schema(self, schema: dict) -> dict:
        """构建分页响应的 OpenAPI schema。

        Args:
            schema: 原始数据项的 schema 定义。

        Returns:
            包含 code、detail、data 字段的 schema 字典。
        """
        return build_object_type(
            properties={
                'code': build_basic_type(OpenApiTypes.NUMBER),
                'detail': build_basic_type(OpenApiTypes.STR),
                'data': build_object_type(
                    properties={'total': build_basic_type(OpenApiTypes.NUMBER), 'results': schema}
                ),
            }
        )


class DynamicPageNumber(object):
    """动态分页器工厂，允许在运行时自定义最大页大小和默认页大小。"""

    def __init__(self, max_page_size: int = 100, page_size: int = 20) -> None:
        """初始化动态分页配置。

        Args:
            max_page_size: 最大允许的每页条数。
            page_size: 默认每页条数。
        """
        self.max_page_size = max_page_size
        self.page_size = page_size

    def __call__(self, *args: Any, **kwargs: Any) -> PageNumber:
        """创建并返回一个配置好的 ``PageNumber`` 实例。

        Returns:
            应用了动态分页参数的 ``PageNumber`` 实例。
        """
        instance = PageNumber()
        instance.max_page_size = self.max_page_size
        instance.page_size = self.page_size
        return instance
