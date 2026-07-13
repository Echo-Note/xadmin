"""服务基类模块，定义服务进程启动、停止、监控、日志轮转等通用抽象行为。"""


import abc
import datetime
import shutil
import subprocess
import threading
from typing import Any

import psutil

from ..hands import *


class BaseService(object):
    """服务基类，封装子进程管理、PID 文件、日志及状态监控的通用逻辑。"""

    def __init__(self, **kwargs) -> None:
        """初始化服务实例。

        Args:
            **kwargs: 必须包含 ``name`` 键，标识服务名称。
        """
        self.name = kwargs['name']
        self._process = None
        self.STOP_TIMEOUT = 10
        self.max_retry = 3
        self.retry = 0
        self.LOG_KEEP_DAYS = 7
        self.EXIT_EVENT = threading.Event()

    @property
    @abc.abstractmethod
    def cmd(self) -> list:
        """启动命令列表，由子类实现。"""
        return []

    @property
    @abc.abstractmethod
    def cwd(self) -> str:
        """工作目录，由子类实现。"""
        return ''

    @property
    def is_running(self) -> bool:
        """判断服务进程是否正在运行。"""
        if self.pid == 0:
            return False
        try:
            os.kill(self.pid, 0)
        except (OSError, ProcessLookupError):
            return False
        else:
            return True

    def show_status(self) -> None:
        """打印服务运行状态，停止时在 DEBUG 模式下输出手动启动命令。"""
        if self.is_running:
            msg = f'{self.name} is running: {self.pid}.'
        else:
            msg = f'{self.name} is stopped.'
            if DEBUG:
                msg = '\033[31m{} is stopped.\033[0m\nYou can manual start it to find the error: \n' \
                      '  $ cd {}\n' \
                      '  $ {}'.format(self.name, self.cwd, ' '.join(self.cmd))

        print(msg)

    # -- log --
    @property
    def log_filename(self) -> str:
        """返回日志文件名。"""
        return f'{self.name}.log'

    @property
    def log_filepath(self) -> str:
        """返回日志文件完整路径。"""
        return os.path.join(LOG_DIR, self.log_filename)

    @property
    def log_file(self) -> Any:
        """以追加模式打开日志文件并返回文件对象。"""
        return open(self.log_filepath, 'a')

    @property
    def log_dir(self) -> str:
        """返回日志文件所在目录。"""
        return os.path.dirname(self.log_filepath)

    # -- end log --

    # -- pid --
    @property
    def pid_filepath(self) -> str:
        """返回 PID 文件完整路径。"""
        return os.path.join(TMP_DIR, f'{self.name}.pid')

    @property
    def pid(self) -> int:
        """读取服务 PID，PID 文件不存在或无效时返回 0。"""
        if not os.path.isfile(self.pid_filepath):
            return 0
        with open(self.pid_filepath) as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                pid = 0
        return pid

    def write_pid(self) -> None:
        """将当前进程 PID 写入 PID 文件。"""
        with open(self.pid_filepath, 'w') as f:
            f.write(str(self.process.pid))

    def remove_pid(self) -> None:
        """删除 PID 文件（若存在）。"""
        if os.path.isfile(self.pid_filepath):
            os.unlink(self.pid_filepath)

    # -- end pid --

    # -- process --
    @property
    def process(self) -> Any:
        """返回 psutil 进程对象，进程不存在时返回 None。"""
        if not self._process:
            try:
                self._process = psutil.Process(self.pid)
            except:
                pass
        return self._process

    # -- end process --

    # -- action --
    def open_subprocess(self) -> None:
        """以子进程方式启动服务命令，输出重定向到日志文件。"""
        kwargs = {'cwd': self.cwd, 'stderr': self.log_file, 'stdout': self.log_file}
        self._process = subprocess.Popen(self.cmd, **kwargs)

    def start(self) -> None:
        """启动服务：若已在运行则跳过，否则启动子进程并写入 PID。"""
        if self.is_running:
            self.show_status()
            return
        self.remove_pid()
        self.open_subprocess()
        self.write_pid()
        self.start_other()

    def start_other(self) -> None:
        """启动服务后的额外操作（子类可覆盖）。"""
        pass

    def stop(self, force: bool = False) -> None:
        """停止服务进程。

        Args:
            force: 是否强制终止（发送 SIGKILL）。
        """
        if not self.is_running:
            self.show_status()
            # self.remove_pid()
            return

        print(f'Stop service: {self.name}', end='')
        sig = 9 if force else 15
        os.kill(self.pid, sig)

        if self.process is None:
            print("\033[31m No process found\033[0m")
            return
        try:
            self.process.wait(1)
        except:
            pass

        for i in range(self.STOP_TIMEOUT):
            if i == self.STOP_TIMEOUT - 1:
                print("\033[31m Error\033[0m")
            if not self.is_running:
                print("\033[32m Ok\033[0m")
                self.remove_pid()
                break
            else:
                continue

    def watch(self) -> None:
        """监控服务状态：检查运行状态、必要时重启、执行日志轮转。"""
        self._check()
        if not self.is_running:
            self._restart()
        self._rotate_log()

    def _check(self) -> None:
        """检查并打印服务当前运行状态。"""
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{now} Check service status: {self.name} -> ", end='')
        if self.process:
            try:
                self.process.wait(1)  # 不wait，子进程可能无法回收
            except:
                pass

        if self.is_running:
            print(f'running at {self.pid}')
        else:
            print(f'stopped at {self.pid}')

    def _restart(self) -> None:
        """重启服务，超过最大重试次数则设置退出事件。"""
        if self.retry > self.max_retry:
            print("Service start failed, exit: {}".format(self.name))
            self.EXIT_EVENT.set()
            return
        self.retry += 1
        print(f'> Find {self.name} stopped, retry {self.retry}, {self.pid}')
        self.start()

    def _rotate_log(self) -> None:
        """在每日 23:59 时轮转日志文件，并清理过期日志。"""
        now = datetime.datetime.now()
        _time = now.strftime('%H:%M')
        if _time != '23:59':
            return

        backup_date = now.strftime('%Y-%m-%d')
        backup_log_dir = os.path.join(self.log_dir, backup_date)
        if not os.path.exists(backup_log_dir):
            os.mkdir(backup_log_dir)

        backup_log_path = os.path.join(backup_log_dir, self.log_filename)
        if os.path.isfile(self.log_filepath) and not os.path.isfile(backup_log_path):
            print(f'Rotate log file: {self.log_filepath} => {backup_log_path}')
            shutil.copy(self.log_filepath, backup_log_path)
            with open(self.log_filepath, 'w') as f:
                pass

        to_delete_date = now - datetime.timedelta(days=self.LOG_KEEP_DAYS)
        to_delete_dir = os.path.join(LOG_DIR, to_delete_date.strftime('%Y-%m-%d'))
        if os.path.exists(to_delete_dir):
            print(f'Remove old log: {to_delete_dir}')
            shutil.rmtree(to_delete_dir, ignore_errors=True)
    # -- end action --
