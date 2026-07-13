"""创建验证码池的管理命令。"""
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.captcha.models import CaptchaStore


class Command(BaseCommand):
    """创建一批随机验证码并加入池中。"""

    help = "Create a pool of random captchas."

    def add_arguments(self, parser: CommandParser) -> None:
        """添加命令行参数。"""
        parser.add_argument(
            "--pool-size",
            type=int,
            default=1000,
            help="Number of new captchas to create, default=1000",
        )
        parser.add_argument(
            "--cleanup-expired",
            action="store_true",
            default=True,
            help="Cleanup expired captchas after creating new ones",
        )

    @transaction.atomic
    def handle(self, **options) -> None:
        """执行创建验证码池的逻辑。"""
        verbose = int(options.get("verbosity"))
        count = options.get("pool_size")
        CaptchaStore.create_pool(count)
        verbose and self.stdout.write("Created %d new captchas\n" % count)
        options.get("cleanup_expired") and CaptchaStore.remove_expired()
        options.get("cleanup_expired") and verbose and self.stdout.write(
            "Expired captchas cleaned up\n"
        )
