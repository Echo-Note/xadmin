# -*- coding: utf-8 -*-
#
"""项目级常量定义模块，包含项目路径、版本号及全局配置实例。"""
import os

from .conf import ConfigManager

__all__ = ['PROJECT_DIR', 'VERSION', 'CONFIG', 'LOG_DIR', 'TMP_DIR', 'CELERY_LOG_DIR']

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_DIR, "data", "logs")
TMP_DIR = os.path.join(PROJECT_DIR, "tmp")
CELERY_LOG_DIR = os.path.join(LOG_DIR, "task")
VERSION = '4.2.1'
CONFIG = ConfigManager.load_user_config()
