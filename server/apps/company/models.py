"""公司主体管理的模型定义。

Company 作为独立 app，可被 cloud_platform 等其他应用通过外键引用。
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel


class Company(DbAuditModel):
    """公司主体，用于标识业务归属的企业/组织。

    其他应用（如云平台管理、项目管理等）可通过 ForeignKey 关联到此模型，
    实现统一的公司主体管理。
    """

    name = models.CharField(max_length=128, verbose_name=_("公司名称"), unique=True)
    short_name = models.CharField(
        max_length=64, verbose_name=_("简称"),
        null=True, blank=True,
        help_text=_("公司简称，方便列表展示"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("启用状态"))

    class Meta:
        verbose_name = _("公司主体")
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self) -> str:
        return self.short_name or self.name
