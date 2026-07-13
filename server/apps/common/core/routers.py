#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : routers
# author : ly_13
# date : 7/31/2024
"""自定义 DRF 路由器，提供不包含 detail 路由的简化路由配置。"""

from collections.abc import Callable

from rest_framework.routers import SimpleRouter, Route, DynamicRoute


class NoDetailRouter(SimpleRouter):
    """不生成 detail 路由的简化路由器，仅保留 list 级别的路由映射。"""

    routes = [
        # List route.
        Route(
            url=r'^{prefix}{trailing_slash}$',
            mapping={
                'post': 'create',
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy',
            },
            name='{basename}-detail',
            detail=False,
            initkwargs={'suffix': 'Instance'},
        ),
        # Dynamically generated list routes. Generated using
        # @action(detail=False) decorator on methods of the viewset.
        DynamicRoute(
            url=r'^{prefix}/{url_path}{trailing_slash}$', name='{basename}-{url_name}', detail=False, initkwargs={}
        ),
    ]

    def __init__(self, *args: object, **kwargs: object) -> None:
        """初始化路由器，参数透传给父类 ``SimpleRouter``。"""
        super().__init__(*args, **kwargs)
