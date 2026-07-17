"""资产管理信号处理器 —— 域名创建/更新时自动同步 Filing 记录。"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.asset.models import Domain, Filing
from apps.common.utils import get_logger

logger = get_logger(__name__)


@receiver(post_save, sender=Domain)
def auto_create_filing_on_domain_save(
    sender: type[Domain],
    instance: Domain,
    created: bool,
    **kwargs,
) -> None:
    """域名创建时自动创建对应的 Filing 备案记录。

    仅在 Domain 首次创建或 Filing 不存在时创建新的 Filing 记录。
    已存在的 Filing 不会重复创建或覆盖。
    """
    Filing.objects.get_or_create(
        domain=instance,
        defaults={
            'company': instance.company,
            'icp_status': 'not_filed',
            'ps_status': 'not_filed',
        },
    )
