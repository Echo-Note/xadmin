#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : common
# author : ly_13
# date : 9/14/2024
"""通用工具模块，提供日志、系统指标、网络连通性及文本转换等公共函数。"""

import logging
import os
import socket

import html2text
import psutil


def get_logger(name: str = '') -> logging.Logger:
    """根据名称获取 xadmin 项目日志记录器。

    Args:
        name: 模块名称，支持文件路径自动提取 basename。

    Returns:
        日志记录器实例。
    """
    if '/' in name:
        name = os.path.basename(name).replace('.py', '')
    return logging.getLogger(f'xadmin.{name}')


def get_disk_usage(path: str) -> float:
    """获取指定路径的磁盘使用率。

    Args:
        path: 磁盘路径。

    Returns:
        磁盘使用率百分比。
    """
    return psutil.disk_usage(path=path).percent


def get_boot_time() -> float:
    """获取系统启动时间戳。"""
    return psutil.boot_time()


def get_cpu_percent() -> float:
    """获取 CPU 使用率百分比。"""
    return psutil.cpu_percent()


def get_cpu_load() -> float:
    """获取单个 CPU 核心的 1 分钟平均负载。

    Returns:
        单核 1 分钟平均负载（保留两位小数）。
    """
    cpu_load_1, cpu_load_5, cpu_load_15 = psutil.getloadavg()
    cpu_count = psutil.cpu_count()
    single_cpu_load_1 = cpu_load_1 / cpu_count
    single_cpu_load_1 = '%.2f' % single_cpu_load_1
    return float(single_cpu_load_1)


def get_docker_mem_usage_if_limit() -> float | None:
    """获取 Docker 容器在内存限制下的内存使用率。

    读取 cgroup 内存信息计算使用率，若未设置内存限制则返回 None。

    Returns:
        内存使用率百分比，无限制时返回 None。
    """
    try:
        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes') as f:
            limit_in_bytes = int(f.readline())
            total = psutil.virtual_memory().total
            if limit_in_bytes >= total:
                raise ValueError('Not limit')

        with open('/sys/fs/cgroup/memory/memory.usage_in_bytes') as f:
            usage_in_bytes = int(f.readline())

        with open('/sys/fs/cgroup/memory/memory.stat') as f:
            inactive_file = 0
            for line in f:
                if line.startswith('total_inactive_file'):
                    name, inactive_file = line.split()
                    break

                if line.startswith('inactive_file'):
                    name, inactive_file = line.split()
                    continue

            inactive_file = int(inactive_file)
        return ((usage_in_bytes - inactive_file) / limit_in_bytes) * 100

    except Exception:
        return None


def get_memory_usage() -> float:
    """获取内存使用率，优先使用 Docker 限制下的使用率。

    Returns:
        内存使用率百分比。
    """
    usage = get_docker_mem_usage_if_limit()
    if usage is not None:
        return usage
    return psutil.virtual_memory().percent


def test_ip_connectivity(host: str, port: int, timeout: float = 0.5) -> bool:
    """测试指定主机和端口的 TCP 连通性。

    Args:
        host: 目标主机地址。
        port: 目标端口。
        timeout: 连接超时时间（秒）。

    Returns:
        连通返回 True，否则返回 False。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((host, int(port)))
    sock.close()
    if result == 0:
        connectivity = True
    else:
        connectivity = False
    return connectivity


def convert_html_to_markdown(html_str: str) -> str:
    """将 HTML 字符串转换为 Markdown 文本。

    Args:
        html_str: HTML 字符串。

    Returns:
        转换后的 Markdown 文本。
    """
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = False

    markdown = h.handle(html_str)
    markdown = markdown.replace('\n\n', '\n')
    markdown = markdown.replace('\n ', '\n')
    return markdown
