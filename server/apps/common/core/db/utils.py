#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : utils
# author : ly_13
# date : 12/18/2023
"""数据库工具模块，提供关联管理器、查询过滤构造及安全的数据库连接上下文管理器。"""
import ipaddress
import re
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from django.db import connections, transaction, connection
from django.db.models import Model, Q, QuerySet


class RelatedManager:
    """关联关系管理器，用于构造数据权限过滤条件和操作关联字段值。"""

    def __init__(self, instance: Model, field: Any) -> None:
        """初始化关联管理器。

        Args:
            instance: 模型实例对象。
            field: 关联字段对象。
        """
        self.instance = instance
        self.field = field
        self.value: Any = None

    def set(self, value: Any) -> None:
        """设置关联字段的值并同步到实例属性。

        Args:
            value: 要设置的值。
        """
        self.value = value
        self.instance.__dict__[self.field.name] = value

    @staticmethod
    def get_ip_in_q(name: str, val: str | list) -> Q:
        """构造 IP 地址相关的 Q 查询条件。

        支持单 IP、IP 段（``-`` 分隔）、CIDR 网段（``/`` 分隔）及前缀匹配。

        Args:
            name: 查询字段名。
            val: IP 值，可为字符串或列表，``['*']`` 表示匹配全部。

        Returns:
            构造好的 ``Q`` 查询对象。
        """
        q = Q()
        if isinstance(val, str):
            val = [val]
        if ['*'] in val:
            return Q()
        for ip in val:
            if not ip:
                continue
            try:
                if '/' in ip:
                    network = ipaddress.ip_network(ip)
                    ips = network.hosts()
                    q |= Q(**{'{}__in'.format(name): ips})
                elif '-' in ip:
                    start_ip, end_ip = ip.split('-')
                    start_ip = ipaddress.ip_address(start_ip)
                    end_ip = ipaddress.ip_address(end_ip)
                    q |= Q(**{'{}__range'.format(name): (start_ip, end_ip)})
                elif len(ip.split('.')) == 4:
                    q |= Q(**{'{}__exact'.format(name): ip})
                else:
                    q |= Q(**{'{}__startswith'.format(name): ip})
            except ValueError:
                continue
        return q

    @classmethod
    def get_filter_attrs_qs(cls, rules: list) -> list[Q]:
        """根据过滤规则列表构造 Q 查询对象列表。

        Args:
            rules: 过滤规则列表，每条规则为包含 field、value、match 等键的字典。

        Returns:
            与规则对应的 ``Q`` 对象列表。
        """
        filters = []
        for attr in rules:
            if not isinstance(attr, dict):
                continue

            name = attr.get('field')
            val = attr.get('value')
            match = attr.get('match', 'exact')
            if name is None or val is None:
                continue

            if match == 'all':
                filters.append(Q())
                continue

            if match == 'ip_in':
                q = cls.get_ip_in_q(name, val)
            elif match in ('contains', 'startswith', 'endswith', 'gte', 'lte', 'gt', 'lt'):
                lookup = '{}__{}'.format(name, match)
                q = Q(**{lookup: val})
            elif match == 'regex':
                try:
                    re.compile(val)
                    lookup = '{}__{}'.format(name, match)
                    q = Q(**{lookup: val})
                except re.error:
                    q = Q(pk__isnull=True)
            # elif match == "not":
            #     q = ~Q(**{name: val})
            elif match.startswith('m2m'):
                if not isinstance(val, list):
                    val = [val]
                if match == 'm2m_all':
                    for v in val:
                        filters.append(Q(**{'{}__in'.format(name): [v]}))
                    continue
                else:
                    q = Q(**{'{}__in'.format(name): val})
            elif match == 'in':
                if not isinstance(val, list):
                    val = [val]
                q = Q() if '*' in val else Q(**{'{}__in'.format(name): val})
            else:
                # q = Q() if val == '*' else Q(**{name: val})
                if val == '*':
                    q = Q()
                else:
                    lookup = '{}__{}'.format(name, match)
                    q = Q(**{lookup: val})
            if attr.get('exclude'):
                q = ~q
            filters.append(q)
        return filters


def close_old_connections(**kwargs: object) -> None:
    """关闭所有不可用或过期的数据库连接。

    Args:
        **kwargs: 预留参数，便于作为信号回调使用。
    """
    for conn in connections.all(initialized_only=True):
        conn.close_if_unusable_or_obsolete()


# 这个要是在 Django 请求周期外使用的，不能影响 Django 的事务管理， 在 api 中使用会影响 api 事务
@contextmanager
def safe_db_connection() -> Generator[None]:
    """安全的数据库连接上下文管理器。

    在进入和退出时关闭过期连接，适用于 Django 请求周期外的数据库操作场景。
    """
    close_old_connections()
    yield
    close_old_connections()


@contextmanager
def safe_atomic_db_connection(auto_close: bool = False) -> Generator[None]:
    """通用数据库连接管理器（线程安全、事务感知）。

    - 在连接不可用时主动重建连接
    - 在非事务环境下自动关闭连接（可选）
    - 不影响 Django 请求/事务周期

    Args:
        auto_close: 是否在退出时强制关闭连接。
    """
    in_atomic = connection.in_atomic_block  # 当前是否在事务中
    autocommit = transaction.get_autocommit()
    recreated = False

    try:
        if not connection.is_usable():
            connection.close()
            connection.connect()
            recreated = True
        yield
    finally:
        # 只在非事务、autocommit 模式下，才考虑主动清理连接
        if auto_close or (recreated and not in_atomic and autocommit):
            close_old_connections()


@contextmanager
def open_db_connection(alias: str = 'default') -> Generator:
    """打开指定别名的数据库连接并在事务中执行。

    Args:
        alias: 数据库连接别名，默认为 ``default``。
    """
    connection = transaction.get_connection(alias)
    try:
        connection.connect()
        with transaction.atomic():
            yield connection
    finally:
        connection.close()
