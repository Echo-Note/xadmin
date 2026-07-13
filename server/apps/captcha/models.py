"""验证码存储模型。"""
import datetime
import hashlib
import random
import time
from collections.abc import Callable

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.encoding import smart_str

from apps.captcha.helpers import get_challenge

# Heavily based on session key generation in Django
# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, "SystemRandom"):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange
MAX_RANDOM_KEY = 18446744073709551616  # 2 << 63

from apps.common.utils import get_logger

logger = get_logger(__name__)


class CaptchaStore(models.Model):
    """验证码存储模型，保存验证码的挑战、响应及过期时间。"""

    id = models.AutoField(primary_key=True)
    challenge = models.CharField(blank=False, max_length=32)
    response = models.CharField(blank=False, max_length=32)
    hashkey = models.CharField(blank=False, max_length=40, unique=True)
    expiration = models.DateTimeField(blank=False)

    def save(self, *args, **kwargs) -> None:
        """保存验证码记录，自动生成 hashkey 并设置过期时间。"""
        self.response = self.response.lower()
        if not self.expiration:
            self.expiration = timezone.now() + datetime.timedelta(
                minutes=int(settings.CAPTCHA_TIMEOUT)
            )
        if not self.hashkey:
            key_ = (
                    smart_str(randrange(0, MAX_RANDOM_KEY))
                    + smart_str(time.time())
                    + smart_str(self.challenge, errors="ignore")
                    + smart_str(self.response, errors="ignore")
            ).encode("utf8")
            self.hashkey = hashlib.sha1(key_).hexdigest()
            del key_
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """返回验证码的挑战字符串。"""
        return self.challenge

    def remove_expired(cls) -> None:
        """删除所有已过期的验证码记录。"""
        cls.objects.filter(expiration__lte=timezone.now()).delete()

    remove_expired = classmethod(remove_expired)

    @classmethod
    def generate_key(cls, generator: str | Callable | None = None) -> str:
        """生成新的验证码并返回其 hashkey。

        Args:
            generator: 验证码挑战生成函数的路径或可调用对象。

        Returns:
            新生成的验证码 hashkey。
        """
        challenge, response = get_challenge(generator)()
        store = cls.objects.create(challenge=challenge, response=response)

        return store.hashkey

    @classmethod
    def pick(cls) -> str:
        """从验证码池中随机取出一个未过期的验证码 hashkey。

        Returns:
            验证码 hashkey。
        """
        if not settings.CAPTCHA_GET_FROM_POOL:
            return cls.generate_key()

        def fallback() -> str:
            logger.error("Couldn't get a captcha from pool, generating")
            return cls.generate_key()

        # Pick up a random item from pool
        minimum_expiration = timezone.now() + datetime.timedelta(
            minutes=int(settings.CAPTCHA_GET_FROM_POOL_TIMEOUT)
        )
        store = (
            cls.objects.filter(expiration__gt=minimum_expiration).order_by("?").first()
        )

        return (store and store.hashkey) or fallback()

    @classmethod
    def create_pool(cls, count: int = 1000) -> None:
        """创建指定数量的验证码并加入池中。

        Args:
            count: 要创建的验证码数量。
        """
        assert count > 0
        while count > 0:
            cls.generate_key()
            count -= 1
