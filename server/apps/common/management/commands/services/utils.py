"""服务管理工具类模块，提供服务进程启动、停止、重启、监控及守护进程管理。"""


import signal
import threading
from typing import Any

import daemon
from daemon import pidfile

from .hands import *
from .services.base import BaseService


class ServicesUtil(object):
    """服务管理工具类，封装多服务的启动、停止、重启、监控与守护进程逻辑。"""

    def __init__(self, services: list, run_daemon: bool = False, force_stop: bool = False, stop_daemon: bool = False) -> None:
        """初始化服务工具实例。

        Args:
            services: 服务对象列表。
            run_daemon: 是否以守护进程模式运行。
            force_stop: 是否强制停止服务。
            stop_daemon: 是否停止守护进程。
        """
        self._services = services
        self.run_daemon = run_daemon
        self.force_stop = force_stop
        self.stop_daemon = stop_daemon
        self.EXIT_EVENT = threading.Event()
        self.check_interval = 30
        self.files_preserve_map = {}

    def restart(self) -> None:
        """重启所有服务：先停止再启动并监控。"""
        self.stop()
        time.sleep(5)
        self.start_and_watch()

    def start_and_watch(self) -> None:
        """启动服务并进入监控循环，守护进程模式下在守护上下文中监控。"""
        print(time.ctime())
        print(f'server now start')
        self.start()
        if self.run_daemon:
            self.show_status()
            with self.daemon_context:
                self.watch()
        else:
            self.watch()

    def start(self) -> None:
        """启动所有服务，根据服务类型执行对应的前置准备。"""
        check_db_status = False
        if 'gunicorn' in [service.name for service in self._services]:
            server_prepare()
            check_db_status = True
        if not check_db_status and {'celery_default', 'beat'} & set([service.name for service in self._services]):
            celery_prepare()
        for service in self._services:
            service: BaseService
            service.start()
            self.files_preserve_map[service.name] = service.log_file

        time.sleep(1)

    def stop(self) -> None:
        """停止所有服务，必要时停止守护进程。"""
        for service in self._services:
            service: BaseService
            service.stop(force=self.force_stop)

        if self.stop_daemon:
            self._stop_daemon()

    # -- watch --
    def watch(self) -> None:
        """监控服务运行状态，直到退出事件触发或服务异常退出。"""
        while not self.EXIT_EVENT.is_set():
            try:
                _exit = self._watch()
                if _exit:
                    break
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                print('Start stop services')
                break
        self.clean_up()

    def _watch(self) -> bool:
        """单次监控检查，若任一服务退出则设置退出事件。

        Returns:
            是否有服务退出。
        """
        for service in self._services:
            service: BaseService
            service.watch()
            if service.EXIT_EVENT.is_set():
                self.EXIT_EVENT.set()
                return True
        return False

    # -- end watch --

    def clean_up(self) -> None:
        """清理资源：设置退出事件并停止所有服务。"""
        if not self.EXIT_EVENT.is_set():
            self.EXIT_EVENT.set()
        self.stop()

    def show_status(self) -> None:
        """打印所有服务的运行状态。"""
        for service in self._services:
            service: BaseService
            service.show_status()

    # -- daemon --
    def _stop_daemon(self) -> None:
        """停止守护进程并移除 PID 文件。"""
        if self.daemon_pid and self.daemon_is_running:
            os.kill(self.daemon_pid, 15)
        self.remove_daemon_pid()

    def remove_daemon_pid(self) -> None:
        """删除守护进程 PID 文件（若存在）。"""
        if os.path.isfile(self.daemon_pid_filepath):
            os.unlink(self.daemon_pid_filepath)

    @property
    def daemon_pid(self) -> int:
        """读取守护进程 PID，PID 文件不存在或无效时返回 0。"""
        if not os.path.isfile(self.daemon_pid_filepath):
            return 0
        with open(self.daemon_pid_filepath) as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                pid = 0
        return pid

    @property
    def daemon_is_running(self) -> bool:
        """判断守护进程是否正在运行。"""
        try:
            os.kill(self.daemon_pid, 0)
        except (OSError, ProcessLookupError):
            return False
        else:
            return True

    @property
    def daemon_pid_filepath(self) -> str:
        """返回守护进程 PID 文件路径。"""
        return os.path.join(TMP_DIR, 'server.pid')

    @property
    def daemon_log_filepath(self) -> str:
        """返回守护进程日志文件路径。"""
        return os.path.join(LOG_DIR, 'server.log')

    @property
    def daemon_context(self) -> Any:
        """构建并返回守护进程上下文对象。"""
        daemon_log_file = open(self.daemon_log_filepath, 'a')
        context = daemon.DaemonContext(
            pidfile=pidfile.TimeoutPIDLockFile(self.daemon_pid_filepath),
            signal_map={
                signal.SIGTERM: lambda x, y: self.clean_up(),
                signal.SIGHUP: 'terminate',
            },
            stdout=daemon_log_file,
            stderr=daemon_log_file,
            files_preserve=list(self.files_preserve_map.values()),
            detach_process=True,
        )
        return context
    # -- end daemon --
