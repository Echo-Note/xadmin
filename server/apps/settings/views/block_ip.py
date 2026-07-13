#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : block_ip
# author : ly_13
# date : 8/12/2024
"""IP 封锁列表视图集定义。"""

import socket
import struct

from django.conf import settings
from django.core.cache import cache

from apps.common.core.modelset import ListDeleteModelSet
from apps.settings.models import Setting
from apps.settings.serializers.security import SecurityBlockIPSerializer
from apps.settings.utils.security import LoginIpBlockUtil


class FilterIps(list):
    """可过滤的 IP 列表。"""

    def filter(self, pk__in: list = None) -> list:
        """根据主键列表过滤 IP。

        Args:
            pk__in: 主键列表。

        Returns:
            过滤后的 IP 列表。
        """
        if pk__in is None:
            pk__in = []
        return [obj.get('ip') for obj in self.__iter__() if obj.get('pk')() in pk__in]


class IpUtils(object):
    """IP 地址与整数互转工具类。"""

    def __init__(self, ip: str) -> None:
        """初始化 IP 工具。

        Args:
            ip: IP 地址字符串。
        """
        self.ip = ip

    def ip_to_int(self) -> str:
        """将 IP 地址转换为整数的字符串表示。"""
        return str(struct.unpack("!I", socket.inet_aton(self.ip))[0])

    def int_to_ip(self) -> str:
        """将整数字符串转换为 IP 地址。"""
        return socket.inet_ntoa(struct.pack("!I", int(self.ip)))


class SecurityBlockIpViewSet(ListDeleteModelSet):
    """IP 拦截名单视图集。"""

    serializer_class = SecurityBlockIPSerializer
    queryset = Setting.objects.none()

    def filter_queryset(self, obj: list) -> FilterIps:
        """重写过滤方法，构造包含 IP 和封锁时间的列表。

        Args:
            obj: 原始查询结果。

        Returns:
            可过滤的 IP 列表。
        """
        # 为啥写函数，去没有加(), 因为只有在序列化的时候，才会判断，如果是方法就执行，减少资源浪费
        data = [{'ip': ip, 'pk': IpUtils(ip).ip_to_int, 'created_time': LoginIpBlockUtil(ip).get_block_info} for ip in
                obj]
        return FilterIps(data)

    def get_queryset(self) -> list:
        """从缓存中获取被封锁的 IP 列表。"""
        ips = []
        prefix = LoginIpBlockUtil.BLOCK_KEY_TMPL.replace('{}', '')
        keys = cache.keys(f'{prefix}*')
        for key in keys:
            ips.append(key.replace(prefix, ''))

        white_list = settings.SECURITY_LOGIN_IP_WHITE_LIST
        ips = list(set(ips) - set(white_list))
        ips = [ip for ip in ips if ip != '*']
        return ips

    def get_object(self) -> str:
        """根据主键获取对应的 IP 地址。"""
        return IpUtils(self.kwargs.get("pk")).int_to_ip()

    def perform_destroy(self, ip: str) -> tuple:
        """删除指定 IP 的封锁记录。

        Args:
            ip: 要解封的 IP 地址。

        Returns:
            tuple: (1, 1) 表示成功。
        """
        LoginIpBlockUtil(ip).clean_block_if_need()
        return 1, 1
