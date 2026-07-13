"""Celery 默认队列服务模块。"""


from .celery_base import CeleryBaseService

__all__ = ['CeleryDefaultService']


class CeleryDefaultService(CeleryBaseService):
    """Celery 默认队列（celery）的 Worker 服务。"""

    def __init__(self, **kwargs) -> None:
        """初始化默认队列服务，将队列名设为 ``celery``。"""
        kwargs['queue'] = 'celery'
        super().__init__(**kwargs)
