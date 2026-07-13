#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : startup
# author : ly_13
# date : 9/14/2024
"""服务器终端心跳与监控启动模块。"""

import os
import socket
import threading
import time

from django.conf import settings

from apps.common.core.db.utils import close_old_connections
from apps.common.decorators import Singleton
from apps.common.serializers import MonitorSerializer
from apps.common.utils import get_cpu_load, get_memory_usage, get_disk_usage, get_boot_time, get_cpu_percent


class BaseTerminal(object):
    """终端基类，负责心跳上报与监控数据采集。"""

    def __init__(self, suffix_name: str, _type: str) -> None:
        """初始化终端实例。

        Args:
            suffix_name: 终端名称后缀。
            _type: 终端类型。
        """
        server_hostname = os.environ.get('SERVER_HOSTNAME') or ''
        hostname = socket.gethostname()
        if server_hostname:
            name = f'[{suffix_name}]-{server_hostname}'
        else:
            name = f'[{suffix_name}]-{hostname}'
        self.name = name
        self.interval = 30
        self.remote_addr = self.get_remote_addr(hostname)
        self.type = _type

    @staticmethod
    def get_remote_addr(hostname: str) -> str:
        """根据主机名获取 IP 地址，解析失败返回 127.0.0.1。

        Args:
            hostname: 主机名。

        Returns:
            IP 地址字符串。
        """
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            return '127.0.0.1'

    def start_heartbeat_thread(self) -> None:
        """启动心跳上报守护线程。"""
        print(f'- Start heartbeat thread => ({self.name})')
        t = threading.Thread(target=self.start_heartbeat, daemon=True)
        t.start()

    def start_heartbeat(self) -> None:
        """循环采集并上报服务器性能监控数据。"""
        while True:
            heartbeat_data = {
                'cpu_load': get_cpu_load(),
                'cpu_percent': get_cpu_percent(),
                'memory_used': get_memory_usage(),
                'disk_used': get_disk_usage(path=settings.PROJECT_DIR),
                'boot_time': get_boot_time(),
            }
            status_serializer = MonitorSerializer(data=heartbeat_data)
            status_serializer.is_valid()

            try:
                status_serializer.save()
                time.sleep(self.interval)
            except Exception:
                print("Save status error, close old connections")
                close_old_connections()
            finally:
                time.sleep(self.interval)


@Singleton
class CoreTerminal(BaseTerminal):
    """核心终端，单例模式。"""

    def __init__(self) -> None:
        """初始化核心终端。"""
        super().__init__(suffix_name='Core', _type='core')

