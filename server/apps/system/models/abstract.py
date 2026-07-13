"""数据权限模式类型抽象模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class ModeTypeAbstract(models.Model):
    """数据权限模式类型抽象模型，定义 AND/OR 两种权限匹配模式。"""

    class ModeChoices(models.IntegerChoices):
        """数据权限模式选择：OR（满足任一规则）或 AND（满足全部规则）。"""

        OR = 0, _("Or mode")
        AND = 1, _("And mode")

    mode_type = models.SmallIntegerField(choices=ModeChoices, default=ModeChoices.OR,
                                         verbose_name=_("Data permission mode"),
                                         help_text=_(
                                             "Permission mode, and the mode indicates that the data needs to satisfy each rule in the rule list at the same time, or the mode satisfies any rule"))

    class Meta:
        """抽象模型元数据配置。"""

        abstract = True
