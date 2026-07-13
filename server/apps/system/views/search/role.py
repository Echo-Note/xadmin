"""角色搜索视图。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import OnlyListModelSet
from apps.common.utils import get_logger
from apps.system.models import UserRole
from apps.system.serializers.role import RoleSerializer

logger = get_logger(__name__)


class SearchRoleFilter(BaseFilterSet):
    """角色搜索过滤器。"""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    code = filters.CharFilter(field_name='code', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = UserRole
        fields = ['name', 'code', 'is_active', 'description']


class SearchRoleSerializer(RoleSerializer):
    """角色搜索序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserRole
        fields = ['pk', 'name', 'code', 'is_active', 'description', 'updated_time']
        read_only_fields = [x.name for x in UserRole._meta.fields]


class SearchRoleViewSet(OnlyListModelSet):
    """角色搜索视图集。"""

    queryset = UserRole.objects.all()
    serializer_class = SearchRoleSerializer
    ordering_fields = ['updated_time', 'name', 'created_time']
    filterset_class = SearchRoleFilter
