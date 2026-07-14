"""系统配置模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel


class BaseConfig(DbAuditModel):
    """配置基类模型，包含配置值、启用状态和 API 访问权限。"""

    value = models.JSONField(max_length=10240, verbose_name=_("Config value"), help_text=_("Configuration value stored in JSON format"), db_comment="配置值，JSON格式存储")
    is_active = models.BooleanField(default=True, verbose_name=_("Is active"), help_text=_("Whether this configuration item is enabled"), db_comment="是否启用")
    access = models.BooleanField(default=False, verbose_name=_("API access"),
                                 help_text=_("Allows API interfaces to access this config"),
                                 db_comment="是否允许API接口访问此配置")

    class Meta:
        """抽象模型元数据配置。"""

        abstract = True


class SystemConfig(BaseConfig, DbUuidModel):
    """系统配置模型，存储全局配置项。"""

    key = models.CharField(max_length=255, unique=True, verbose_name=_("Config name"), help_text=_("Unique configuration key name"), db_comment="配置键名，唯一标识")
    inherit = models.BooleanField(default=False, verbose_name=_("User inherit"),
                                  help_text=_("Allows users to inherit this config"),
                                  db_comment="是否允许用户继承此配置")

    class Meta:
        """系统配置元数据。"""

        verbose_name = _("System config")
        verbose_name_plural = verbose_name
        db_table_comment = "系统全局配置表"

    def __str__(self) -> str:
        """返回配置键和描述的字符串表示。"""
        return '%s-%s' % (self.key, self.description)


class UserPersonalConfig(BaseConfig):
    """用户个人配置模型，存储每个用户的个性化配置。"""

    owner = models.ForeignKey('system.UserInfo', verbose_name=_('User'), on_delete=models.CASCADE, help_text=_("The user who owns this personal configuration"), db_comment="配置所属用户")
    key = models.CharField(max_length=255, verbose_name=_('Config name'), help_text=_("Configuration key name for this user's personal setting"), db_comment="配置键名")

    class Meta:
        """用户个人配置元数据。"""

        verbose_name = _('User config')
        verbose_name_plural = verbose_name
        unique_together = (('owner', 'key'),)
        db_table_comment = "用户个人配置表"

    def __str__(self) -> str:
        """返回配置键和描述的字符串表示。"""
        return '%s-%s' % (self.key, self.description)
