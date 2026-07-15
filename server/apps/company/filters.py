"""公司主体管理的过滤器定义。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.company.choices import CompanyTypeChoices
from apps.company.models import Company


class CompanyFilter(BaseFilterSet):
    """公司主体过滤器。"""

    pk = filters.CharFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    short_name = filters.CharFilter(field_name='short_name', lookup_expr='icontains')
    unified_social_credit_code = filters.CharFilter(
        field_name='unified_social_credit_code',
        lookup_expr='icontains',
    )
    company_type = filters.ChoiceFilter(
        field_name='company_type',
        lookup_expr='exact',
        choices=CompanyTypeChoices.choices,
    )
    legal_representative = filters.CharFilter(
        field_name='legal_representative',
        lookup_expr='icontains',
    )
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        """过滤器元数据配置。"""

        model = Company
        fields = [
            'name',
            'short_name',
            'unified_social_credit_code',
            'company_type',
            'legal_representative',
            'is_active',
        ]
