"""使配置缓存失效的管理命令。"""

from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser

from apps.common.core.config import ConfigCacheBase


class Command(BaseCommand):
    """使配置缓存失效的 Django 管理命令。"""

    help = 'Expire config caches'

    def add_arguments(self, parser: CommandParser) -> None:
        """添加命令行参数。

        Args:
            parser: 命令行参数解析器。
        """
        parser.add_argument('key', nargs='?', type=str, default='*')

    def handle(self, *args, **options) -> None:
        """执行命令，使指定 key 的系统配置和用户配置缓存失效。"""
        ConfigCacheBase().invalid_config_cache(options.get('key', '*'))
        ConfigCacheBase(px='user').invalid_config_cache(options.get('key', '*'))
