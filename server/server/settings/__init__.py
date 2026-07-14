"""Django 设置包，聚合 base、custom、libs、logging、setting、storage 各模块配置。"""
from .base import *
from .custom import *
from .libs import *
from .logging import *
from .setting import *
from .storage import *  # 存储设置须在 base 之后加载（依赖 CONFIG）
