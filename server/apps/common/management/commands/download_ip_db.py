"""下载 IP 数据库的管理命令模块。"""


from django.core.management.base import BaseCommand, CommandParser

from apps.common.management.commands.services.hands import download_ip_db


class Command(BaseCommand):
    """下载 IP 数据库的 Django 管理命令。"""

    help = 'Download IP database'

    def add_arguments(self, parser: CommandParser) -> None:
        """添加命令行参数。

        Args:
            parser: argparse 参数解析器。
        """
        parser.add_argument('-f', '--force', nargs="?", help="force download database", default=False, const=True)

    def handle(self, *args, **options) -> None:
        """执行下载 IP 数据库逻辑。

        Args:
            *args: 位置参数。
            **options: 命令行选项字典。
        """
        download_ip_db(force=options['force'])
