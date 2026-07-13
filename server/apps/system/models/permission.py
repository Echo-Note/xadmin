"""权限模型。"""


from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel, DbCharModel
from apps.system.models import ModeTypeAbstract


class DataPermission(DbAuditModel, ModeTypeAbstract, DbUuidModel):
    """数据权限模型，定义基于规则的数据过滤策略。"""

    name = models.CharField(verbose_name=_('Name'), max_length=255, unique=True)
    rules = models.JSONField(verbose_name=_('Rules'), max_length=10240)
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True)
    menu = models.ManyToManyField('system.Menu', verbose_name=_('Menu'), blank=True,
                                  help_text=_('If a menu exists, it only applies to the selected menu permission'))

    class Meta:
        """数据权限元数据。"""

        ordering = ('-created_time',)
        verbose_name = _('Data permission')
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        """返回数据权限名称的字符串表示。"""
        return f'{self.name}'


class FieldPermission(DbAuditModel, DbCharModel):
    """字段权限模型，控制角色对菜单中字段的访问权限。"""

    role = models.ForeignKey('system.UserRole', on_delete=models.CASCADE, verbose_name=_('Role'))
    menu = models.ForeignKey('system.Menu', on_delete=models.CASCADE, verbose_name=_('Menu'))
    field = models.ManyToManyField('system.ModelLabelField', verbose_name=_('Field'), blank=True)

    class Meta:
        """字段权限元数据。"""

        verbose_name = _('Field permission')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        unique_together = ('role', 'menu')

    def save(self, *args, **kwargs) -> None:
        """保存前根据角色和菜单 ID 自动生成主键。

        Args:
            *args: 传递给父类 save 的位置参数。
            **kwargs: 传递给父类 save 的关键字参数。
        """
        self.id = f'{self.role.pk}-{self.menu.pk}'
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """返回主键、角色名和创建时间的字符串表示。"""
        return f'{self.pk}-{self.role.name}-{self.created_time}'
