"""服务管理命令基类模块，定义服务枚举与启动/停止/重启/状态查看的通用命令。"""


import multiprocessing
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import TextChoices

from .hands import *
from .utils import ServicesUtil


class Services(TextChoices):
    """可管理的服务类型枚举。"""

    gunicorn = 'gunicorn', 'gunicorn'
    celery_default = 'celery_default', 'celery_default'
    beat = 'beat', 'beat'
    flower = 'flower', 'flower'
    web = 'web', 'web'
    celery = 'celery', 'celery'
    task = 'task', 'task'
    all = 'all', 'all'

    @classmethod
    def get_service_object_class(cls, name: str) -> Any:
        """根据服务名称返回对应的服务类。

        Args:
            name: 服务名称。

        Returns:
            服务类对象，未找到时返回 None。
        """
        from . import services
        services_map = {
            cls.gunicorn.value: services.GunicornService,
            cls.flower: services.FlowerService,
            cls.celery_default: services.CeleryDefaultService,
            cls.beat: services.BeatService
        }
        return services_map.get(name)

    @classmethod
    def web_services(cls) -> list:
        """返回 Web 相关服务列表。"""
        return [cls.gunicorn, cls.flower]

    @classmethod
    def celery_services(cls) -> list:
        """返回 Celery 相关服务列表。"""
        return [cls.celery_default]

    @classmethod
    def task_services(cls) -> list:
        """返回任务相关服务列表（Celery + Beat）。"""
        return cls.celery_services() + [cls.beat]

    @classmethod
    def all_services(cls) -> list:
        """返回所有服务列表。"""
        return cls.web_services() + cls.task_services()

    @classmethod
    def export_services_values(cls) -> list:
        """返回所有可用的服务名称值列表，用于命令行参数 choices。"""
        return [cls.all.value, cls.web.value, cls.task.value] + [s.value for s in cls.all_services()]

    @classmethod
    def get_service_objects(cls, service_names: list, **kwargs) -> list:
        """根据服务名称列表创建服务对象列表。

        Args:
            service_names: 服务名称列表。
            **kwargs: 传递给服务类构造函数的额外参数。

        Returns:
            服务对象列表。
        """
        services = set()
        for name in service_names:
            method_name = f'{name}_services'
            if hasattr(cls, method_name):
                _services = getattr(cls, method_name)()
            elif hasattr(cls, name):
                _services = [getattr(cls, name)]
            else:
                continue
            services.update(set(_services))

        service_objects = []
        for s in services:
            service_class = cls.get_service_object_class(s.value)
            if not service_class:
                continue
            kwargs.update({
                'name': s.value
            })
            service_object = service_class(**kwargs)
            service_objects.append(service_object)
        return service_objects


class Action(TextChoices):
    """服务操作动作枚举。"""

    start = 'start', 'start'
    status = 'status', 'status'
    stop = 'stop', 'stop'
    restart = 'restart', 'restart'


class BaseActionCommand(BaseCommand):
    """服务管理命令基类，提供启动/停止/重启/查看状态的通用实现。"""

    help = 'Service Base Command'

    action = None
    util = None

    def __init__(self, *args, **kwargs) -> None:
        """初始化命令实例。"""
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser: CommandParser) -> None:
        """添加命令行参数。

        Args:
            parser: argparse 参数解析器。
        """
        cores = GUNICORN_MAX_WORKER
        if (multiprocessing.cpu_count() * 2 + 1) < cores:
            cores = multiprocessing.cpu_count() * 2 + 1

        parser.add_argument(
            'services', nargs='+', choices=Services.export_services_values(), help='Service',
        )
        parser.add_argument('-d', '--daemon', nargs="?", const=True)
        parser.add_argument('-w', '--worker', type=int, nargs="?", default=cores)
        parser.add_argument('-f', '--force', nargs="?", const=True)

    def initial_util(self, *args, **options) -> None:
        """根据命令行选项初始化服务工具实例。

        Args:
            *args: 位置参数。
            **options: 命令行选项字典。
        """
        service_names = options.get('services')
        service_kwargs = {
            'worker_gunicorn': options.get('worker')
        }
        services = Services.get_service_objects(service_names=service_names, **service_kwargs)

        kwargs = {
            'services': services,
            'run_daemon': options.get('daemon', False),
            'stop_daemon': self.action == Action.stop.value and Services.all.value in service_names,
            'force_stop': options.get('force') or False,
        }
        self.util = ServicesUtil(**kwargs)

    def handle(self, *args, **options) -> None:
        """根据 action 执行对应的服务操作。

        Args:
            *args: 位置参数。
            **options: 命令行选项字典。
        """
        self.initial_util(*args, **options)
        assert self.action in Action.values, f'The action {self.action} is not in the optional list'
        _handle = getattr(self, f'_handle_{self.action}', lambda: None)
        _handle()

    def _handle_start(self) -> None:
        """启动服务并进入监控循环。"""
        self.util.start_and_watch()
        os._exit(0)

    def _handle_stop(self) -> None:
        """停止服务。"""
        self.util.stop()

    def _handle_restart(self) -> None:
        """重启服务。"""
        self.util.restart()

    def _handle_status(self) -> None:
        """查看服务状态。"""
        self.util.show_status()
