"""测试用 Django 设置，继承开发环境全部配置。"""
from .base import *      # noqa: F403
from .custom import *    # noqa: F403
from .libs import *      # noqa: F403
from .logging import *   # noqa: F403
from .setting import *   # noqa: F403
from .storage import *   # noqa: F403

# 测试期间不启用调试日志
DEBUG = False
LOG_LEVEL = 'ERROR'

# Celery 同步执行
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
