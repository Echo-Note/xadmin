#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : response
# author : ly_13
# date : 6/2/2023
"""统一 API 响应封装，提供标准化的响应数据结构。"""

import datetime
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework.response import Response

from server.utils import get_current_request


class ApiResponse(Response):
    """统一 API 响应类，封装业务状态码、详情、数据等标准字段。"""

    def __init__(
        self,
        code: int = 1000,
        detail: str | None = None,
        data: Any = None,
        status: int | None = None,
        headers: dict | None = None,
        content_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        """初始化统一响应对象。

        Args:
            code: 业务状态码，默认 1000 表示成功。
            detail: 响应详情描述，为空时根据 code 自动填充成功/失败提示。
            data: 响应业务数据。
            status: HTTP 状态码。
            headers: 响应头信息。
            content_type: 响应内容类型。
            **kwargs: 其他需要追加到响应体中的扩展字段。
        """
        dic = {
            'code': code,
            'detail': detail if detail else (_('Operation successful') if code == 1000 else _('Operation failed')),
            'requestId': str(getattr(get_current_request(), 'request_uuid', '')),
            'timestamp': str(datetime.datetime.now()),
        }
        if data is not None:
            dic['data'] = data
        dic.update(kwargs)
        self._data = data
        # 对象来调用对象的绑定方法，会自动传值
        super().__init__(data=dic, status=status, headers=headers, content_type=content_type)

        # 类来调用对象的绑定方法，这个方法就是一个普通函数，有几个参数就要传几个参数
        # Response.__init__(data=dic,status=status,headers=headers,content_type=content_type)
