"""云平台管理应用的过滤器定义。"""

from django_filters import rest_framework as filters

from apps.cloud_platform.choices import PlatformTypeChoices, CredentialTypeChoices
from apps.cloud_platform.models import CloudPlatform, Credential
from apps.common.core.filter import BaseFilterSet
from apps.company.models import Company


class CloudPlatformFilter(BaseFilterSet):
    """云平台实例过滤器。"""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    platform_type = filters.ChoiceFilter(
        field_name='platform_type', lookup_expr='exact',
        choices=PlatformTypeChoices.choices,
    )
    company = filters.ModelChoiceFilter(
        field_name='company', lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = CloudPlatform
        fields = ['name', 'platform_type', 'company', 'is_active']


class CredentialFilter(BaseFilterSet):
    """凭据过滤器。"""

    platform = filters.CharFilter(field_name='platform__pk', lookup_expr='exact')
    credential_type = filters.ChoiceFilter(
        field_name='credential_type', lookup_expr='exact',
        choices=CredentialTypeChoices.choices,
    )
    credential_name = filters.CharFilter(field_name='credential_name', lookup_expr='icontains')
    username = filters.CharFilter(field_name='username', lookup_expr='icontains')
    email = filters.CharFilter(field_name='email', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        model = Credential
        fields = ['platform', 'credential_type', 'credential_name', 'username', 'email', 'is_active']
