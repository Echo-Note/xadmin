"""停止服务的命令模块。"""


from .services.command import BaseActionCommand, Action


class Command(BaseActionCommand):
    """停止服务的 Django 管理命令。"""

    help = 'Stop services'
    action = Action.stop.value
