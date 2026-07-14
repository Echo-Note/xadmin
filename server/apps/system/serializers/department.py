"""部门序列化器。"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import DeptInfo

logger = get_logger(__name__)


class DeptSerializer(BaseModelSerializer):
    """部门序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = DeptInfo
        fields = [
            'pk', 'name', 'code', 'parent', 'rank', 'is_active', 'roles', 'user_count', 'rules', 'mode_type',
            'auto_bind', 'description', 'created_time'
        ]

        table_fields = [
            'name', 'pk', 'code', 'user_count', 'rank', 'mode_type', 'auto_bind', 'is_active', 'roles', 'rules',
            'created_time'
        ]

        extra_kwargs = {
            'roles': {'required': False, 'attrs': ['pk', 'name', 'code'], 'format': '{name}', 'many': True,
                       'label': _('Role permission'),
                       'help_text': _('Roles associated with the department')},
            'rules': {'required': False, 'attrs': ['pk', 'name', 'get_mode_type_display'], 'format': '{name}',
                      'many': True, 'label': _('Data permission'),
                      'help_text': _('Data permission rules associated with the department')},
            'parent': {'required': False, 'attrs': ['pk', 'name', 'parent_id'],
                       'label': _('Superior department'),
                       'help_text': _('Parent department of the current department, null for top-level')},
            'pk': {'read_only': True, 'label': _('ID'), 'help_text': _('Primary key ID')},
            'name': {'label': _('Department name'), 'help_text': _('Name of the department')},
            'code': {'label': _('Department code'),
                     'help_text': _('Unique code identifying the department')},
            'rank': {'label': _('Rank'), 'help_text': _('Sort order of the department')},
            'is_active': {'label': _('Is active'),
                          'help_text': _('Whether the department is active')},
            'mode_type': {'label': _('Data permission mode'),
                          'help_text': _('Permission mode, AND means all rules must be satisfied, OR means any rule')},
            'auto_bind': {'label': _('Auto bind'),
                          'help_text': _('If the value of the registration parameter channel is consistent with the department code, the user is automatically bound to the department')},
            'description': {'label': _('Description'),
                            'help_text': _('Description of the department')},
            'created_time': {'label': _('Created time'),
                             'help_text': _('Creation time of the department')},
        }

    user_count = serializers.SerializerMethodField(read_only=True, label=_('User count'),
                                                    help_text=_('Number of users belonging to the department'))

    def validate(self, attrs: dict) -> dict:
        """验证部门数据，移除权限相关字段并确保上级部门存在。

        Args:
            attrs: 待验证的属性字典。

        Returns:
            验证后的属性字典。
        """
        # 权限需要其他接口设置，下面三个参数忽略
        attrs.pop('rules', None)
        attrs.pop('roles', None)
        attrs.pop('mode_type', None)
        # 上级部门必须存在，否则会出现数据权限问题
        parent = attrs.get('parent', self.instance.parent if self.instance else None)
        if not parent:
            attrs['parent'] = self.request.user.dept
        return attrs

    def update(self, instance: DeptInfo, validated_data: dict) -> DeptInfo:
        """更新部门信息，防止将上级部门设为自身的子部门。

        Args:
            instance: 待更新的 DeptInfo 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 DeptInfo 实例。
        """
        parent = validated_data.get('parent')
        if parent and str(parent.pk) in DeptInfo.recursion_dept_info(dept_id=instance.pk):
            raise ValidationError(_('The superior department cannot be its own subordinate department'))
        return super().update(instance, validated_data)

    @extend_schema_field(serializers.IntegerField)
    def get_user_count(self, obj: DeptInfo) -> int:
        """获取部门下的用户数量。

        Args:
            obj: DeptInfo 模型实例。

        Returns:
            部门下的用户数量。
        """
        return obj.userinfo_set.count()
