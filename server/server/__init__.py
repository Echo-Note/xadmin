"""xadmin 服务端包，确保 Django 启动时自动导入 Celery 应用。"""
# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)
