"""权限序列化器。"""

from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import DataPermission, Menu

logger = get_logger(__name__)


def get_menu_queryset() -> QuerySet:
    """获取权限类型菜单及其父级菜单的查询集。

    Returns:
        排序后的菜单查询集。
    """
    queryset = Menu.objects
    pks = queryset.filter(menu_type=Menu.MenuChoices.PERMISSION).values_list('parent', flat=True)
    return queryset.filter(Q(menu_type=Menu.MenuChoices.PERMISSION) | Q(id__in=pks)).order_by('rank')


class DataPermissionSerializer(BaseModelSerializer):
    """数据权限序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = DataPermission
        fields = ['pk', 'name', 'is_active', 'mode_type', 'menu', 'description', 'rules', 'created_time']
        table_fields = ['pk', 'name', 'mode_type', 'is_active', 'description', 'created_time']
        extra_kwargs = {
            'menu': {
                'attrs': ['pk', 'name', 'parent_id', 'meta__title'],
                'many': True, 'required': False, 'queryset': get_menu_queryset(),
                'label': _('Menu'),
                'help_text': _('If a menu exists, it only applies to the selected menu permission')
            },
            'pk': {'read_only': True, 'label': _('ID'), 'help_text': _('Primary key ID')},
            'name': {'label': _('Name'), 'help_text': _('Name of the data permission')},
            'is_active': {'label': _('Is active'), 'help_text': _('Whether the data permission is active')},
            'mode_type': {'label': _('Data permission mode'),
                          'help_text': _('Permission mode, AND means all rules must be satisfied, OR means any rule')},
            'rules': {'label': _('Rules'), 'help_text': _('Data permission rule list for filtering data')},
            'description': {'label': _('Description'), 'help_text': _('Description of the data permission')},
            'created_time': {'label': _('Created time'),
                             'help_text': _('Creation time of the data permission')},
        }

    def validate(self, attrs: dict) -> dict:
        """验证数据权限规则，确保规则非空且规则数小于 2 时强制 OR 模式。

        Args:
            attrs: 待验证的属性字典。

        Returns:
            验证后的属性字典。
        """
        rules = attrs.get('rules', [] if not self.instance else self.instance.rules)
        if not rules:
            raise ValidationError(_('The rule cannot be null'))
        if len(rules) < 2:
            attrs['mode_type'] = DataPermission.ModeChoices.OR
        return attrs
