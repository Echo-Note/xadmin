"""数据权限管理视图。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.utils import get_logger
from apps.system.models import DataPermission
from apps.system.serializers.permission import DataPermissionSerializer

logger = get_logger(__name__)


class DataPermissionFilter(BaseFilterSet):
    """数据权限过滤器。"""

    pk = filters.UUIDFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = DataPermission
        fields = ['pk', 'name', 'mode_type', 'is_active', 'description']


class DataPermissionViewSet(BaseModelSet, ImportExportDataAction):
    """数据权限视图集。"""

    queryset = DataPermission.objects.all()
    serializer_class = DataPermissionSerializer
    ordering_fields = ['created_time']
    filterset_class = DataPermissionFilter
