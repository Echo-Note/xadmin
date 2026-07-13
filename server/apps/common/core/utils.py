#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : utils
# author : ly_13
# date : 6/2/2023
"""核心工具模块，提供 URL 路由解析、日志格式化及拓扑排序等通用功能。"""
import datetime
import logging
import re
from collections import OrderedDict, deque, defaultdict
from typing import Any

from django.apps import apps
from django.conf import settings
from django.http import QueryDict, HttpRequest
from django.urls import URLPattern, URLResolver
from django.utils.module_loading import import_string
from django.utils.termcolors import make_style

from apps.common.base.magic import import_from_string
from apps.common.decorators import cached_method

logger = logging.getLogger(__name__)


def check_show_url(url: str) -> bool | None:
    """检查 URL 是否匹配权限展示前缀。

    Args:
        url: 待检查的 URL 字符串。

    Returns:
        匹配成功返回 True，否则返回 None。
    """
    for prefix in settings.PERMISSION_SHOW_PREFIX:
        if re.match(prefix, url):
            return True


def ignore_white_url(url: str) -> bool | None:
    """检查 URL 是否匹配忽略白名单前缀。

    Args:
        url: 待检查的 URL 字符串。

    Returns:
        匹配成功返回 True，否则返回 None。
    """
    for prefix in settings.ROUTE_IGNORE_URL:
        if re.match(prefix, f"/{url.replace('$', '')}"):
            return True


def recursion_urls(pre_namespace: str | None, pre_url: str, urlpatterns: list,
                   url_ordered_dict: OrderedDict) -> None:
    """递归去获取URL
    :param pre_namespace: namespace前缀，以后用户拼接name
    :param pre_url: url前缀，以后用于拼接url
    :param urlpatterns: 路由关系列表
    :param url_ordered_dict: 用于保存递归中获取的所有路由
    """
    for item in urlpatterns:
        if isinstance(item, URLPattern):
            if not item.name:
                continue

            if pre_namespace:
                name = "%s:%s" % (pre_namespace, item.name)
            else:
                name = item.name
            url = pre_url + item.pattern.regex.pattern.lstrip('^')
            # url = url.replace('^', '').replace('$', '')

            if check_show_url(url) and not ignore_white_url(url):
                url_ordered_dict[name] = {'name': name, 'url': url, 'view': item.lookup_str}
                try:
                    view_set = import_string(item.lookup_str)
                    url_ordered_dict[name]['label'] = view_set.__doc__
                except Exception:
                    pass


        elif isinstance(item, URLResolver):  # 路由分发，递归操作
            new_pre_url = pre_url + item.pattern.regex.pattern.lstrip('^')
            if not check_show_url(new_pre_url):
                continue
            if pre_namespace:
                if item.namespace:
                    namespace = "%s:%s" % (pre_namespace, item.namespace)
                else:
                    namespace = item.namespace
            else:
                if item.namespace:
                    namespace = item.namespace
                else:
                    namespace = None
            recursion_urls(namespace, new_pre_url, item.url_patterns, url_ordered_dict)


@cached_method(ttl=-1)
def get_all_url_dict(pre_url: str = '/') -> Any:
    """
       获取项目中所有的URL（必须有name别名）
    """
    url_ordered_dict = OrderedDict()
    md = import_string(settings.ROOT_URLCONF)
    url_ordered_dict['#'] = {'name': '#', 'url': '#', 'view': '#', 'label': '#'}
    recursion_urls(None, pre_url, md.urlpatterns, url_ordered_dict)  # 递归去获取所有的路由
    return url_ordered_dict.values()


def auto_register_app_url(urlpatterns: list) -> None:
    """自动注册 xadmin 应用的 URL 路由及权限白名单。

    Args:
        urlpatterns: 待追加路由的 URL 列表。
    """
    xadmin_apps = []
    for app in settings.XADMIN_APPS:
        if '.' in app:
            xadmin_apps.append(import_string(app).name)
        else:
            xadmin_apps.append(app)
    # xadmin_apps = [x.split('.')[0] for x in settings.XADMIN_APPS]
    for name, value in apps.app_configs.items():
        if name not in xadmin_apps: continue

        # 使用 value.name 替代 name，以正确处理 apps.xxxx.apps.XxxxConfig 这样的嵌套结构
        app_module_name = value.name

        urls = import_from_string(f"{app_module_name}.config.URLPATTERNS")
        logger.info(f"auto register {name} url success")
        if urls:
            urlpatterns.extend(urls)
            for url in urls:
                settings.PERMISSION_SHOW_PREFIX.append(url.pattern.regex.pattern.lstrip('^'))
            settings.PERMISSION_DATA_AUTH_APPS.append(name)

        try:
            urls = import_from_string(f"{app_module_name}.config.PERMISSION_WHITE_REURL")
            if urls:
                settings.PERMISSION_WHITE_URL.update(urls)
        except Exception as e:
            logger.warning(f"auto register {name} permission_white_reurl failed. {e}")


def get_query_post_pks(request: HttpRequest) -> list:
    """从请求数据中获取 pks 列表。

    兼容 QueryDict 和普通 dict 两种数据格式。

    Args:
        request: HTTP 请求对象。

    Returns:
        主键列表，不存在时返回空列表。
    """
    if isinstance(request.data, QueryDict):
        pks = request.data.getlist('pks', [])
    else:
        pks = request.data.get('pks', [])
    return pks


class PrintLogFormat(object):
    """日志格式化打印工具类，支持彩色终端输出及可选的 logger 记录。"""

    def __init__(self, base_str: str = '', title_width: int = 80, body_width: int = 60,
                 logger_enable: bool = False) -> None:
        """初始化日志格式化工具。

        Args:
            base_str: 日志前缀字符串。
            title_width: 标题列宽度，小于 1 时不做对齐。
            body_width: 内容列宽度，小于 1 时不做对齐。
            logger_enable: 是否同时通过 logger 记录日志。
        """
        self.base_str = base_str
        self.logger_enable = logger_enable
        self.title_width = title_width
        self.body_width = body_width
        self.bold_error = make_style(opts=('bold',), fg='magenta')
        self._info = make_style(fg='green')
        self._error = make_style(fg='red')
        self._warning = make_style(fg='yellow')
        self._debug = make_style(fg='blue')

    def __print(self, title: str, body: str) -> None:
        """格式化打印日志标题和内容。

        Args:
            title: 日志标题。
            body: 日志内容。
        """
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{now} {title}" if self.title_width < 1 else '{0: <{title_width}}'.format(f"{now} {title}",
                                                                                         title_width=self.title_width),
              body if self.body_width < 1 else '{0: >{body_width}}'.format(body, body_width=self.body_width))

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """记录 INFO 级别日志。

        Args:
            msg: 日志消息。
            *args: 透传给 logger 的位置参数。
            **kwargs: 透传给 logger 的关键字参数。
        """
        if self.logger_enable:
            logger.info(f"{self.base_str} {msg}", *args, **kwargs)
        if logger.isEnabledFor(logging.INFO):
            self.__print(self.bold_error(self.base_str), self._info(msg))

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """记录 ERROR 级别日志。

        Args:
            msg: 日志消息。
            *args: 透传给 logger 的位置参数。
            **kwargs: 透传给 logger 的关键字参数。
        """
        if self.logger_enable:
            logger.error(f"{self.base_str} {msg}", *args, **kwargs)
        if logger.isEnabledFor(logging.ERROR):
            self.__print(self.bold_error(self.base_str), self._error(msg))

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """记录 DEBUG 级别日志。

        Args:
            msg: 日志消息。
            *args: 透传给 logger 的位置参数。
            **kwargs: 透传给 logger 的关键字参数。
        """
        if self.logger_enable:
            logger.debug(f"{self.base_str} {msg}", *args, **kwargs)
        if logger.isEnabledFor(logging.DEBUG):
            self.__print(self.bold_error(self.base_str), self._debug(msg))

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """记录 WARNING 级别日志。

        Args:
            msg: 日志消息。
            *args: 透传给 logger 的位置参数。
            **kwargs: 透传给 logger 的关键字参数。
        """
        if self.logger_enable:
            logger.warning(f"{self.base_str} {msg}", *args, **kwargs)
        if logger.isEnabledFor(logging.WARNING):
            self.__print(self.bold_error(self.base_str), self._warning(msg))


def topological_sort(data: list, pk: str = 'pk', parent: str = 'parent') -> list:
    """对数据进行拓扑排序，解决自关联依赖的先后顺序问题。

    Args:
        data: 待排序的数据列表，每项为字典。
        pk: 主键字段名。
        parent: 父级字段名。

    Returns:
        拓扑排序后的数据列表。

    Raises:
        ValueError: 当存在循环依赖时抛出。
    """
    # 构建图和入度表
    graph = defaultdict(list)
    in_degree = {item[pk]: 0 for item in data}
    nodes = set()
    new_data = {}
    for item in data:
        node_id = item[pk]
        new_data[node_id] = item
        parent_id = item[parent]
        if isinstance(parent_id, dict):
            parent_id = item[parent].get(pk)
        nodes.add(node_id)
        if parent_id is not None:
            graph[parent_id].append(node_id)
            if parent_id in in_degree:
                in_degree[node_id] += 1

    # 找到所有入度为0的节点
    queue = deque([node for node in nodes if in_degree[node] == 0])
    sorted_order = []

    while queue:
        current = queue.popleft()
        sorted_order.append(current)
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 如果排序后的列表长度不等于原始列表长度，说明存在环
    if len(sorted_order) != len(nodes):
        raise ValueError("Circular dependencies exist")

    return [new_data[node_id] for node_id in sorted_order]


def has_self_fields(model: Any, keys: list) -> str | None:
    """检查模型是否存在自关联字段。

    仅仅支持判断 ForeignKey 自关联，不支持多对对自关联判断

    Args:
        model: Django 模型类。
        keys: 待检查的字段名列表。

    Returns:
        匹配到的自关联字段名，不存在时返回 None。
    """
    for field in model._meta.fields:
        if field.is_relation and field.related_model is not None and field.related_model == model and field.name in keys:
            return field.name
