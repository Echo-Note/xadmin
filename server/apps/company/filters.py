"""公司主体管理的过滤器定义。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.company.models import Company


class CompanyFilter(BaseFilterSet):
    """公司主体过滤器。"""

    pk = filters.CharFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    short_name = filters.CharFilter(field_name='short_name', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        """过滤器元数据配置。"""

        model = Company
        fields = ['name', 'short_name', 'is_active']
