"""Celery 任务日志处理器。"""
from logging import LogRecord, StreamHandler
from threading import get_ident
from typing import Any

from celery import current_task
from celery.signals import task_prerun, task_postrun

from apps.common.celery.utils import get_celery_task_log_path, CELERY_LOG_MAGIC_MARK


class CeleryTaskLoggerHandler(StreamHandler):
    """Celery 任务日志处理器基类。"""

    terminator = '\r\n'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化处理器并连接任务开始/结束信号。"""
        super().__init__(*args, **kwargs)
        task_prerun.connect(self.on_task_start)
        task_postrun.connect(self.on_start_end)

    @staticmethod
    def get_current_task_id() -> str | None:
        """获取当前 Celery 任务的根 ID。"""
        if not current_task:
            return None
        task_id = current_task.request.root_id
        return task_id

    def on_task_start(self, sender: Any, task_id: str, **kwargs: Any) -> Any:
        """任务开始信号回调。"""
        return self.handle_task_start(task_id)

    def on_start_end(self, sender: Any, task_id: str, **kwargs: Any) -> Any:
        """任务结束信号回调。"""
        return self.handle_task_end(task_id)

    def after_task_publish(self, sender: Any, body: Any, **kwargs: Any) -> None:
        """任务发布后回调。"""
        pass

    def emit(self, record: LogRecord) -> None:
        """输出日志记录。"""
        task_id = self.get_current_task_id()
        if not task_id:
            return
        try:
            self.write_task_log(task_id, record)
            self.flush()
        except Exception:
            self.handleError(record)

    def write_task_log(self, task_id: str, msg: LogRecord) -> None:
        """写入任务日志，子类实现具体逻辑。"""
        pass

    def handle_task_start(self, task_id: str) -> None:
        """处理任务开始，子类实现具体逻辑。"""
        pass

    def handle_task_end(self, task_id: str) -> None:
        """处理任务结束，子类实现具体逻辑。"""
        pass


class CeleryThreadingLoggerHandler(CeleryTaskLoggerHandler):
    """基于线程的 Celery 任务日志处理器。"""

    @staticmethod
    def get_current_thread_id() -> str:
        """获取当前线程标识。"""
        return str(get_ident())

    def emit(self, record: LogRecord) -> None:
        """按线程输出日志记录。"""
        thread_id = self.get_current_thread_id()
        try:
            self.write_thread_task_log(thread_id, record)
            self.flush()
        except ValueError:
            self.handleError(record)

    def write_thread_task_log(self, thread_id: str, record: LogRecord) -> None:
        """写入线程任务日志，子类实现具体逻辑。"""
        pass

    def handle_task_start(self, task_id: str) -> None:
        """处理任务开始，子类实现具体逻辑。"""
        pass

    def handle_task_end(self, task_id: str) -> None:
        """处理任务结束，子类实现具体逻辑。"""
        pass

    def handleError(self, record: LogRecord) -> None:
        """处理日志输出错误。"""
        pass


class CeleryThreadTaskFileHandler(CeleryThreadingLoggerHandler):
    """将 Celery 线程任务日志写入文件处理器。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化文件处理器及线程-文件描述符映射。"""
        self.thread_id_fd_mapper: dict[str, Any] = {}
        self.task_id_thread_id_mapper: dict[str, str] = {}
        super().__init__(*args, **kwargs)

    def write_thread_task_log(self, thread_id: str, record: LogRecord) -> None:
        """将日志记录写入对应线程的日志文件。"""
        f = self.thread_id_fd_mapper.get(thread_id, None)
        if not f:
            raise ValueError('Not found thread task file')
        msg = self.format(record)
        f.write(msg.encode())
        f.write(self.terminator.encode())
        f.flush()

    def flush(self) -> None:
        """刷新所有线程的日志文件描述符。"""
        for f in self.thread_id_fd_mapper.values():
            f.flush()

    def handle_task_start(self, task_id: str) -> None:
        """任务开始时打开日志文件并建立映射。"""
        # log_path = get_celery_task_log_path(task_id.split('_')[0])
        log_path = get_celery_task_log_path(task_id)
        thread_id = self.get_current_thread_id()
        self.task_id_thread_id_mapper[task_id] = thread_id
        f = open(log_path, 'ab')
        self.thread_id_fd_mapper[thread_id] = f

    def handle_task_end(self, task_id: str) -> None:
        """任务结束时关闭日志文件并清理映射。"""
        ident_id = self.task_id_thread_id_mapper.get(task_id, '')
        f = self.thread_id_fd_mapper.pop(ident_id, None)
        if f and not f.closed:
            f.write(CELERY_LOG_MAGIC_MARK)
            f.close()
        self.task_id_thread_id_mapper.pop(task_id, None)

