"""权限模型。"""


from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel, DbCharModel
from apps.system.models import ModeTypeAbstract


class DataPermission(DbAuditModel, ModeTypeAbstract, DbUuidModel):
    """数据权限模型，定义基于规则的数据过滤策略。"""

    name = models.CharField(verbose_name=_('Name'), max_length=255, unique=True, help_text=_('The unique name of the data permission rule'), db_comment="数据权限名称")
    rules = models.JSONField(verbose_name=_('Rules'), max_length=10240, help_text=_('Data filter rules in JSON format, each rule defines field, operator and value'), db_comment="数据权限规则列表，JSON格式")
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True, help_text=_('Whether this data permission rule is currently active'), db_comment="是否启用")
    menu = models.ManyToManyField('system.Menu', verbose_name=_('Menu'), blank=True,
                                  help_text=_('If a menu exists, it only applies to the selected menu permission'))

    class Meta:
        """数据权限元数据。"""

        ordering = ('-created_time',)
        verbose_name = _('Data permission')
        verbose_name_plural = verbose_name
        db_table_comment = "数据权限表，定义基于规则的数据过滤策略"

    def __str__(self) -> str:
        """返回数据权限名称的字符串表示。"""
        return f'{self.name}'


class FieldPermission(DbAuditModel, DbCharModel):
    """字段权限模型，控制角色对菜单中字段的访问权限。"""

    role = models.ForeignKey('system.UserRole', on_delete=models.CASCADE, verbose_name=_('Role'), help_text=_('The user role that this field permission applies to'), db_comment="关联角色")
    menu = models.ForeignKey('system.Menu', on_delete=models.CASCADE, verbose_name=_('Menu'), help_text=_('The menu page whose fields are controlled by this permission'), db_comment="关联菜单")
    field = models.ManyToManyField('system.ModelLabelField', verbose_name=_('Field'), blank=True, help_text=_('The model fields that the role is allowed to access on the menu page'))

    class Meta:
        """字段权限元数据。"""

        verbose_name = _('Field permission')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        unique_together = ('role', 'menu')
        db_table_comment = "字段权限表，控制角色对菜单中字段的访问权限"

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
