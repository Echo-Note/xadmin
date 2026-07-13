"""部门模型。"""

import json

from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework.utils import encoders

from apps.common.core.models import DbAuditModel, DbUuidModel
from apps.system.models import ModeTypeAbstract


class DeptInfo(DbAuditModel, ModeTypeAbstract, DbUuidModel):
    """部门信息模型，支持树形层级结构和数据权限配置。"""

    name = models.CharField(verbose_name=_('Department name'), max_length=128)
    code = models.CharField(max_length=128, verbose_name=_('Department code'), unique=True)
    parent = models.ForeignKey('system.DeptInfo', on_delete=models.PROTECT, verbose_name=_('Superior department'),
                               null=True, blank=True, related_query_name='parent_query')
    roles = models.ManyToManyField('system.UserRole', verbose_name=_('Role permission'), blank=True)
    rules = models.ManyToManyField('system.DataPermission', verbose_name=_('Data permission'), blank=True)
    rank = models.IntegerField(verbose_name=_('Rank'), default=99)
    auto_bind = models.BooleanField(verbose_name=_('Auto bind'), default=False,
                                    help_text=_(
                                        'If the value of the registration parameter channel is consistent with the department code, the user is automatically bound to the department'))
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True)

    @classmethod
    def recursion_dept_info(cls, dept_id: int, dept_all_list: list[dict] | None = None,
                            dept_list: list[int] | None = None, is_parent: bool = False) -> list[int]:
        """递归获取部门的所有子部门或父部门 ID 列表。

        Args:
            dept_id: 起始部门 ID。
            dept_all_list: 所有部门的 pk 和 parent 字典列表，为空时自动查询。
            dept_list: 已收集的部门 ID 列表，为空时初始化为 [dept_id]。
            is_parent: 为 True 时向上查找父部门，为 False 时向下查找子部门。

        Returns:
            所有关联部门的 ID 列表。
        """
        parent = 'parent'
        pk = 'pk'
        if is_parent:
            parent, pk = pk, parent
        if not dept_all_list:
            dept_all_list = DeptInfo.objects.values('pk', 'parent')
        if dept_list is None:
            dept_list = [dept_id]
        for dept in dept_all_list:
            if dept.get(parent) == dept_id:
                if dept.get(pk):
                    dept_list.append(dept.get(pk))
                    cls.recursion_dept_info(dept.get(pk), dept_all_list, dept_list, is_parent)
        return json.loads(json.dumps(list(set(dept_list)), cls=encoders.JSONEncoder))

    class Meta:
        """部门元数据。"""

        verbose_name = _('Department')
        verbose_name_plural = verbose_name
        ordering = ('-rank', '-created_time',)

    def __str__(self) -> str:
        """返回部门名称和主键的字符串表示。"""
        return f'{self.name}({self.pk})'
