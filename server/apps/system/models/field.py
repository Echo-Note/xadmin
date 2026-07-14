"""模型字段标签模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel


class ModelLabelField(DbAuditModel, DbUuidModel):
    """模型字段标签模型，用于定义数据权限规则中可引用的字段。"""

    class KeyChoices(models.TextChoices):
        """字段值类型选择。"""

        TEXT = 'value.text', _('Text')
        JSON = 'value.json', _('Json')
        ALL = 'value.all', _('All data')
        DATETIME = 'value.datetime', _('Datetime')
        DATETIME_RANGE = 'value.datetime.range', _('Datetime range selector')
        DATE = 'value.date', _('Seconds to the current time')
        OWNER = 'value.user.id', _('My ID')
        OWNER_DEPARTMENT = 'value.user.dept.id', _('My department ID')
        OWNER_DEPARTMENTS = 'value.user.dept.ids', _('My department ID and data below the department')
        DEPARTMENTS = 'value.dept.ids', _('Department ID and data below the department')
        TABLE_USER = 'value.table.user.ids', _('Select the user ID')
        TABLE_MENU = 'value.table.menu.ids', _('Select menu ID')
        TABLE_ROLE = 'value.table.role.ids', _('Select role ID')
        TABLE_DEPT = 'value.table.dept.ids', _('Select department ID')

    class FieldChoices(models.IntegerChoices):
        """字段类型选择：角色权限或数据权限。"""

        ROLE = 0, _('Role permission')
        DATA = 1, _('Data permission')

    field_type = models.SmallIntegerField(choices=FieldChoices, default=FieldChoices.DATA, verbose_name=_('Field type'), help_text=_('Field type: 0 for role permission, 1 for data permission'), db_comment="字段类型：0-角色权限 1-数据权限")
    parent = models.ForeignKey('system.ModelLabelField', on_delete=models.CASCADE, null=True, blank=True,
                               verbose_name=_('Parent node'), help_text=_('Parent node in the model field label tree structure'),
                               db_comment="父级节点")
    name = models.CharField(verbose_name=_('Model/Field name'), max_length=128, help_text=_('Identifier name of the model or field, used for matching in permission rules'), db_comment="模型或字段的名称标识")
    label = models.CharField(verbose_name=_('Model/Field label'), max_length=128, help_text=_('Display label of the model or field for user interface rendering'), db_comment="模型或字段的显示标签")

    class Meta:
        """模型字段标签元数据。"""

        ordering = ('-created_time',)
        unique_together = ('name', 'parent')
        verbose_name = _('Model label field')
        verbose_name_plural = verbose_name
        db_table_comment = "模型字段标签表，用于定义数据权限规则中可引用的字段"

    def __str__(self) -> str:
        """返回字段标签和名称的字符串表示。"""
        return f'{self.label}({self.name})'
