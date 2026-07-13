"""角色管理视图。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.utils import get_logger
from apps.system.models import UserRole
from apps.system.serializers.role import RoleSerializer, ListRoleSerializer

logger = get_logger(__name__)


class RoleFilter(BaseFilterSet):
    """角色过滤器。"""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    code = filters.CharFilter(field_name='code', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = UserRole
        fields = ['name', 'code', 'is_active', 'description']


class RoleViewSet(BaseModelSet, ImportExportDataAction):
    """角色视图集。"""

    queryset = UserRole.objects.all()
    serializer_class = RoleSerializer
    list_serializer_class = ListRoleSerializer
    ordering_fields = ['updated_time', 'name', 'created_time']
    filterset_class = RoleFilter
