#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : heatbeat
# author : ly_13
# date : 10/23/2024
"""Celery Worker 心跳状态文件管理。"""
import os.path
import tempfile
from pathlib import Path
from typing import Any

from celery.signals import heartbeat_sent, worker_ready, worker_shutdown

temp_dir = tempfile.gettempdir()


@heartbeat_sent.connect
def heartbeat(sender: Any, **kwargs: Any) -> None:
    """心跳信号触发时创建心跳标记文件。"""
    worker_name = sender.eventer.hostname.split('@')[0]
    heartbeat_path = Path(os.path.join(temp_dir, f'worker_heartbeat_{worker_name}'))
    heartbeat_path.touch()


@worker_ready.connect
def worker_ready(sender: Any, **kwargs: Any) -> None:
    """Worker 就绪信号触发时创建就绪标记文件。"""
    worker_name = sender.hostname.split('@')[0]
    ready_path = Path(os.path.join(temp_dir, f'worker_ready_{worker_name}'))
    ready_path.touch()


@worker_shutdown.connect
def worker_shutdown(sender: Any, **kwargs: Any) -> None:
    """Worker 关闭信号触发时清理就绪与心跳标记文件。"""
    worker_name = sender.hostname.split('@')[0]
    for signal in ['ready', 'heartbeat']:
        path = Path(os.path.join(temp_dir, f'worker_{signal}_{worker_name}'))
        path.unlink(missing_ok=True)

