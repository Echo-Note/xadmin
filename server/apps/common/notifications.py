"""系统通知消息类。"""
from django.db.models.aggregates import Avg
from django.db.models.functions import Round
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from apps.common.models import Monitor
from apps.notifications.backends import BACKEND
from apps.notifications.models import SystemMsgSubscription
from apps.notifications.notifications import SystemMessage, UserMessage
from apps.system.models import UserInfo


class ServerPerformanceMessage(SystemMessage):
    """服务器性能告警消息。"""

    category = 'Monitor'
    category_label = _('Monitor')
    message_type_label = _('Server performance')

    def __init__(self, terms_with_errors: list) -> None:
        """初始化性能告警消息。

        Args:
            terms_with_errors: 存在异常的终端及错误信息列表。
        """
        self.terms_with_errors = terms_with_errors

    def get_html_msg(self) -> dict:
        """生成 HTML 格式的告警消息。"""
        subject = _("Server health check warning")
        context = {
            'terms_with_errors': self.terms_with_errors
        }
        message = render_to_string('monitor/msg_terminal_performance.html', context)
        return {
            'subject': subject,
            'message': message,
        }

    def get_site_msg_msg(self) -> dict:
        """生成站点消息，级别为 danger。"""
        info = self.get_html_msg()
        info['level'] = 'danger'
        return info

    @classmethod
    def post_insert_to_db(cls, subscription: SystemMsgSubscription) -> None:
        """订阅记录入库后，将管理员加入接收人并设置邮件后端。"""
        admins = UserInfo.objects.filter(is_superuser=True, is_active=True)
        subscription.users.add(*admins)
        subscription.receive_backends = [BACKEND.EMAIL]
        subscription.save()

    @classmethod
    def gen_test_msg(cls) -> None:
        """生成测试消息。"""
        pass


class ServerPerformanceCheckUtil(object):
    """服务器性能检查与告警工具类。"""

    items_mapper = {
        'disk_used': {
            'default': 0,
            'max_threshold': 80,
            'alarm_msg_format': _('Disk used more than {max_threshold}%: => {value}')
        },
        'memory_used': {
            'default': 0,
            'max_threshold': 85,
            'alarm_msg_format': _('Memory used more than {max_threshold}%: => {value}'),
        },
        'cpu_load': {
            'default': 0,
            'max_threshold': 5,
            'alarm_msg_format': _('CPU load more than {max_threshold}: => {value}'),
        },
        'cpu_percent': {
            'default': 0,
            'max_threshold': 80,
            'alarm_msg_format': _('CPU percent more than {max_threshold}: => {value}'),
        },
    }

    def __init__(self) -> None:
        """初始化性能检查工具。"""
        self.terms_with_errors: list = []
        self._terminals: list = []

    def check_and_publish(self) -> None:
        """执行性能检查并发布告警消息。"""
        self.check()
        self.publish()

    def check(self) -> None:
        """检查各终端性能指标，收集异常项。"""
        self.terms_with_errors = []
        self.initial_terminals()

        for term in self._terminals:
            errors = self.check_terminal(term)
            if not errors:
                continue
            self.terms_with_errors.append((term, errors))

    def check_terminal(self, term: dict) -> list:
        """检查单个终端的各项性能指标。

        Args:
            term: 终端性能数据字典。

        Returns:
            错误信息列表。
        """
        errors = []
        for item, data in self.items_mapper.items():
            error = self.check_item(term, item, data)
            if not error:
                continue
            errors.append(error)
        return errors

    @staticmethod
    def check_item(term: dict, item: str, data: dict) -> str | None:
        """检查单个性能指标是否超过阈值。

        Args:
            term: 终端性能数据字典。
            item: 指标名。
            data: 指标配置字典。

        Returns:
            超阈值时的告警消息，未超阈值时返回 None。
        """
        default = data['default']
        max_threshold = data['max_threshold']
        value = term.get(item, default)

        if isinstance(value, bool) and value != max_threshold:
            return None
        elif isinstance(value, (int, float)) and value < max_threshold:
            return None
        msg = data['alarm_msg_format']
        error = msg.format(max_threshold=max_threshold, value=value, name='api')
        return error

    def publish(self) -> None:
        """发布性能告警消息。"""
        if not self.terms_with_errors:
            return
        ServerPerformanceMessage(self.terms_with_errors).publish()

    @staticmethod
    def get_monitor_latest_average_value(num: int = 3) -> dict:
        """最近指定次数数据的平均值。

        Args:
            num: 取最近的数据条数。

        Returns:
            各指标平均值字典。
        """
        return Monitor.objects.order_by('-created_time')[0:num].aggregate(
            cpu_load=Round(Avg('cpu_load'), 2),
            cpu_percent=Round(Avg('cpu_percent'), 2),
            memory_used=Round(Avg('memory_used'), 2),
            disk_used=Round(Avg('disk_used'), 2),
        )

    def initial_terminals(self) -> None:
        """初始化终端列表，取最近监控平均值。"""
        self._terminals = [self.get_monitor_latest_average_value()]


class TaskMessage(object):
    """任务消息基类。"""

    def get_html_msg(self) -> dict:
        """生成 HTML 格式的任务消息。"""
        context = dict(
            subject=self.subject,
            name=self.user.nickname,
            **self.task,
        )
        message = render_to_string('notify/msg_task.html', context)
        return {
            'subject': self.subject,
            'message': message
        }


class ImportDataMessage(TaskMessage, UserMessage):
    """数据导入任务消息。"""

    category = 'Task Message'
    category_label = _('Task Message')
    message_type_label = _('Import data message')

    def __init__(self, user: UserInfo, task: dict) -> None:
        """初始化数据导入任务消息。

        Args:
            user: 接收消息的用户。
            task: 任务信息字典。
        """
        super().__init__(user)
        self.task = task
        self.subject = _('Import {} data {} message').format(self.task.get("view_doc"), self.task.get("status"))


class BatchDeleteDataMessage(TaskMessage, UserMessage):
    """批量删除任务消息。"""

    category = 'Task Message'
    category_label = _('Task Message')
    message_type_label = _('Batch delete data message')

    def __init__(self, user: UserInfo, task: dict) -> None:
        """初始化批量删除任务消息。

        Args:
            user: 接收消息的用户。
            task: 任务信息字典。
        """
        super().__init__(user)
        self.task = task
        self.subject = _('Batch delete {} data {} message').format(self.task.get("view_doc"), self.task.get("status"))

