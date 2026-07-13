"""查看服务状态的命令模块。"""


from .services.command import BaseActionCommand, Action


class Command(BaseActionCommand):
    """查看服务状态的 Django 管理命令。"""

    help = 'Show services status'
    action = Action.status.value
