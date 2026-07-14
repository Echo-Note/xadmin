"""公司主体管理的视图集。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet
from apps.company import models
from apps.company.serializers import CompanySerializer


class CompanyFilter(BaseFilterSet):
    """公司主体过滤器。"""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    short_name = filters.CharFilter(field_name='short_name', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = models.Company
        fields = ['name', 'short_name', 'is_active']


class CompanyViewSet(BaseModelSet):
    """公司主体管理"""

    queryset = models.Company.objects.all()
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter
    ordering_fields = ['name', 'created_time']
