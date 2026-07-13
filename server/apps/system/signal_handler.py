"""系统应用信号处理器，管理缓存失效逻辑。"""

import itertools
from collections.abc import Generator
from typing import Any

from django.contrib.auth import user_logged_out
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.common.base.magic import cache_response, MagicCacheData
from apps.common.core.config import SysConfig
from apps.common.utils import get_logger
from apps.system.models import Menu, UserRole, UserInfo, DeptInfo, SystemConfig
from apps.system.signal import invalid_user_cache_signal

logger = get_logger(__name__)


def get_cache_data_keys(pks: list) -> Generator[str]:
    """生成用户权限缓存的键列表。

    Args:
        pks: 用户主键列表。

    Yields:
        各 HTTP 方法对应的缓存键。
    """
    for pk in pks:
        for method in ["GET", "PUT", "DELETE", "POST", "PATCH"]:
            yield f'get_user_permission_{pk}_{method}'


def get_cache_response_keys(pks: list) -> Generator[str]:
    """生成用户路由缓存的键列表。

    Args:
        pks: 用户主键列表。

    Yields:
        路由缓存键。
    """
    for pk in pks:
        yield f'UserRoutesAPIView_get_{pk}'


def batch_invalid_cache(pks: list, batch_length: int = 1000) -> None:
    """批量失效用户缓存。

    Args:
        pks: 用户主键列表。
        batch_length: 每批处理的数量，默认 1000。
    """
    cleans = [
        (MagicCacheData.invalid_caches, get_cache_data_keys(pks)),
        (cache_response.invalid_caches, get_cache_response_keys(pks))
    ]
    for keys in cleans:
        for data in itertools.batched(keys[1], batch_length):
            keys[0](data)


@receiver([post_save, pre_delete], sender=Menu)
def clean_cache_handler(sender: type, instance: Menu, **kwargs: Any) -> None:
    """菜单变更时失效相关用户缓存。

    Args:
        sender: 发送信号的模型类。
        instance: 菜单实例。
        **kwargs: 信号附加参数。
    """
    batch_invalid_cache(UserInfo.objects.filter(is_superuser=True).values_list('pk', flat=True))
    pk1 = UserRole.objects.filter(menu=instance, userinfo__isnull=False).values_list('userinfo', flat=True).distinct()
    pk2 = DeptInfo.objects.filter(roles__menu=instance).values_list('dept_query', flat=True).distinct()
    batch_invalid_cache(set(pk1) | set(pk2))
    logger.info(f"invalid cache {instance}")


@receiver([post_save, pre_delete], sender=SystemConfig)
def invalid_config_cache_handler(sender: type, instance: SystemConfig, **kwargs: Any) -> None:
    """系统配置变更时失效配置缓存。

    Args:
        sender: 发送信号的模型类。
        instance: SystemConfig 实例。
        **kwargs: 信号附加参数。
    """
    SysConfig.invalid_config_cache(instance.key)
    logger.info(f"invalid cache {instance}")


@receiver([post_save, pre_delete], sender=UserRole)
def invalid_role_cache_handler(sender: type, instance: UserRole, **kwargs: Any) -> None:
    """角色变更时失效关联用户缓存。

    Args:
        sender: 发送信号的模型类。
        instance: UserRole 实例。
        **kwargs: 信号附加参数。
    """
    pk1 = instance.userinfo_set.values_list('pk', flat=True).distinct()
    pk2 = DeptInfo.objects.filter(roles=instance).values_list('dept_query', flat=True).distinct()
    batch_invalid_cache(set(pk1) | set(pk2))
    logger.info(f"invalid cache {instance}")


@receiver([post_save, pre_delete], sender=DeptInfo)
def invalid_dept_cache_handler(sender: type, instance: DeptInfo, **kwargs: Any) -> None:
    """部门变更时失效关联用户缓存。

    Args:
        sender: 发送信号的模型类。
        instance: DeptInfo 实例。
        **kwargs: 信号附加参数。
    """
    batch_invalid_cache(instance.userinfo_set.values_list('pk', flat=True).distinct())
    logger.info(f"invalid cache {instance}")


@receiver([post_save, pre_delete], sender=UserInfo)
def invalid_user_cache_handler(sender: type, instance: UserInfo, **kwargs: Any) -> None:
    """用户变更时失效该用户缓存。

    Args:
        sender: 发送信号的模型类。
        instance: UserInfo 实例。
        **kwargs: 信号附加参数。
    """
    batch_invalid_cache([instance.pk])
    logger.info(f"invalid cache {instance}")


# 清理用户相关缓存，用户登出会自动清理
@receiver([invalid_user_cache_signal, user_logged_out])
def invalid_user_cache(sender: type, **kwargs: Any) -> None:
    """用户登出或缓存信号触发时失效用户缓存。

    Args:
        sender: 发送信号的类。
        **kwargs: 信号附加参数，可能包含 user_pk 或 user。
    """
    user_pk = kwargs.get('user_pk', None)
    user = kwargs.get('user', None)
    if isinstance(user, UserInfo):
        user_pk = user.pk
    if user_pk is None:
        return

    batch_invalid_cache([user_pk])
