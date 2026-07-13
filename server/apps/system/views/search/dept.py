"""部门搜索视图。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import OnlyListModelSet
from apps.common.core.pagination import DynamicPageNumber
from apps.common.utils import get_logger
from apps.system.models import DeptInfo
from apps.system.serializers.department import DeptSerializer

logger = get_logger(__name__)


class SearchDeptFilter(BaseFilterSet):
    """部门搜索过滤器。"""

    pk = filters.UUIDFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = DeptInfo
        fields = ['name', 'is_active', 'code', 'description']


class SearchDeptSerializer(DeptSerializer):
    """部门搜索序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = DeptInfo
        fields = ['name', 'pk', 'code', 'parent', 'is_active', 'user_count', 'auto_bind', 'description', 'created_time']
        table_fields = ['name', 'code', 'is_active', 'user_count', 'auto_bind', 'description', 'created_time', 'pk']
        read_only_fields = [x.name for x in DeptInfo._meta.fields]


class SearchDeptViewSet(OnlyListModelSet):
    """部门搜索视图集。"""

    queryset = DeptInfo.objects.all()
    serializer_class = SearchDeptSerializer
    pagination_class = DynamicPageNumber(1000)
    ordering_fields = ['created_time', 'rank']
    filterset_class = SearchDeptFilter
