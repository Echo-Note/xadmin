"""系统配置模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel


class BaseConfig(DbAuditModel):
    """配置基类模型，包含配置值、启用状态和 API 访问权限。"""

    value = models.JSONField(max_length=10240, verbose_name=_("Config value"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is active"))
    access = models.BooleanField(default=False, verbose_name=_("API access"),
                                 help_text=_("Allows API interfaces to access this config"))

    class Meta:
        """抽象模型元数据配置。"""

        abstract = True


class SystemConfig(BaseConfig, DbUuidModel):
    """系统配置模型，存储全局配置项。"""

    key = models.CharField(max_length=255, unique=True, verbose_name=_("Config name"))
    inherit = models.BooleanField(default=False, verbose_name=_("User inherit"),
                                  help_text=_("Allows users to inherit this config"))

    class Meta:
        """系统配置元数据。"""

        verbose_name = _("System config")
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        """返回配置键和描述的字符串表示。"""
        return '%s-%s' % (self.key, self.description)


class UserPersonalConfig(BaseConfig):
    """用户个人配置模型，存储每个用户的个性化配置。"""

    owner = models.ForeignKey('system.UserInfo', verbose_name=_('User'), on_delete=models.CASCADE)
    key = models.CharField(max_length=255, verbose_name=_('Config name'))

    class Meta:
        """用户个人配置元数据。"""

        verbose_name = _('User config')
        verbose_name_plural = verbose_name
        unique_together = (('owner', 'key'),)

    def __str__(self) -> str:
        """返回配置键和描述的字符串表示。"""
        return '%s-%s' % (self.key, self.description)
