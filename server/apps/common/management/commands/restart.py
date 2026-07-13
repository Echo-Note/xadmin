"""重启服务的命令模块。"""


from .services.command import BaseActionCommand, Action


class Command(BaseActionCommand):
    """重启服务的 Django 管理命令。"""

    help = 'Restart services'
    action = Action.restart.value
