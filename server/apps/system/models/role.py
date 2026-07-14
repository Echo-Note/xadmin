"""角色模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel


class UserRole(DbAuditModel, DbUuidModel):
    """用户角色模型，关联菜单权限。"""

    name = models.CharField(max_length=128, verbose_name=_('Role name'), unique=True, help_text=_('The display name of the user role'), db_comment="角色名称")
    code = models.CharField(max_length=128, verbose_name=_('Role code'), unique=True, help_text=_('The unique code identifier of the role, used for programmatic permission checks'), db_comment="角色编码")
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True, help_text=_('Whether this role is currently enabled'), db_comment="是否启用")
    menu = models.ManyToManyField('system.Menu', verbose_name=_('Menu'), blank=True, help_text=_('The menu permissions associated with this role'))

    class Meta:
        """角色元数据。"""

        verbose_name = _('User role')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        db_table_comment = "用户角色表，关联菜单权限"

    def __str__(self) -> str:
        """返回角色名称和代码的字符串表示。"""
        return f'{self.name}({self.code})'
