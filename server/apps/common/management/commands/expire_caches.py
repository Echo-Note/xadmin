"""清除缓存的管理命令模块。"""


from django.core.management.base import BaseCommand, CommandParser

from apps.common.cache.storage import RedisCacheBase


class Command(BaseCommand):
    """清除指定缓存键的 Django 管理命令。"""

    help = 'Expire Caches'

    def add_arguments(self, parser: CommandParser) -> None:
        """添加命令行参数。

        Args:
            parser: argparse 参数解析器。
        """
        parser.add_argument(
            "args", metavar="cache key", nargs="+", help="please input cache key or '*' for delete all keys"
        )

    def handle(self, *args, **options) -> None:
        """执行清除缓存逻辑。

        Args:
            *args: 缓存键列表。
            **options: 命令行选项字典。
        """
        for key in args:
            if key.endswith("*"):
                RedisCacheBase(key).del_many()
            else:
                RedisCacheBase(key).del_storage_cache()
