"""资产管理应用的过滤器定义。"""

from django.db.models import QuerySet
from django_filters import rest_framework as filters

from apps.asset.choices import (
    DnsRecordTypeChoices,
    DomainStatusChoices,
    HypervisorTypeChoices,
    ServerOSTypeChoices,
    ServerStatusChoices,
)
from apps.asset.models import CloudServer, DnsRecord, Domain, LocalServer, LocalVM
from apps.cloud_platform.models import CloudPlatform
from apps.common.core.filter import BaseFilterSet
from apps.company.models import Company


class CloudServerFilter(BaseFilterSet):
    """云服务器资产过滤器。"""

    pk = filters.CharFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    platform = filters.ModelChoiceFilter(
        field_name='platform',
        lookup_expr='exact',
        queryset=CloudPlatform.objects.filter(is_active=True),
    )
    instance_id = filters.CharFilter(field_name='instance_id', lookup_expr='icontains')
    public_ip = filters.CharFilter(field_name='public_ip', lookup_expr='icontains')
    private_ip = filters.CharFilter(field_name='private_ip', lookup_expr='icontains')
    os_type = filters.ChoiceFilter(
        field_name='os_type',
        lookup_expr='exact',
        choices=ServerOSTypeChoices.choices,
    )
    status = filters.ChoiceFilter(
        field_name='status',
        lookup_expr='exact',
        choices=ServerStatusChoices.choices,
    )
    region = filters.CharFilter(field_name='region', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')
    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )

    class Meta:
        """元数据配置。"""

        model = CloudServer
        fields = [
            'name',
            'platform',
            'instance_id',
            'public_ip',
            'private_ip',
            'os_type',
            'status',
            'region',
            'is_active',
            'company',
        ]


class DomainFilter(BaseFilterSet):
    """域名资产过滤器。"""

    pk = filters.CharFilter(field_name='id')
    domain_name = filters.CharFilter(field_name='domain_name', lookup_expr='icontains')
    registrar = filters.CharFilter(field_name='registrar', lookup_expr='icontains')
    platform = filters.ModelChoiceFilter(
        field_name='platform',
        lookup_expr='exact',
        queryset=CloudPlatform.objects.filter(is_active=True),
        label='云平台',
    )
    status = filters.ChoiceFilter(
        field_name='status',
        lookup_expr='exact',
        choices=DomainStatusChoices.choices,
    )
    is_ssl_enabled = filters.BooleanFilter(field_name='is_ssl_enabled')
    is_icp_filed = filters.BooleanFilter(
        field_name='icp_number',
        method='filter_filing_status',
        label='ICP 备案',
    )
    is_ps_filed = filters.BooleanFilter(
        field_name='ps_filing_number',
        method='filter_filing_status',
        label='公安备案',
    )
    is_active = filters.BooleanFilter(field_name='is_active')

    def filter_filing_status(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """按备案号是否为空过滤。True=已备案（非空）。"""
        if value:
            return queryset.exclude(**{name: ''}).filter(**{f'{name}__isnull': False})
        return queryset.filter(**{name: ''}) | queryset.filter(**{f'{name}__isnull': True})

    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )
    expire_time = filters.DateFromToRangeFilter(field_name='expire_time')

    class Meta:
        """元数据配置。"""

        model = Domain
        fields = [
            'domain_name',
            'registrar',
            'platform',
            'status',
            'is_ssl_enabled',
            'is_icp_filed',
            'is_ps_filed',
            'is_active',
            'company',
            'expire_time',
        ]


class LocalServerFilter(BaseFilterSet):
    """本地物理服务器过滤器。"""

    pk = filters.CharFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    hostname = filters.CharFilter(field_name='hostname', lookup_expr='icontains')
    ip_address = filters.CharFilter(field_name='ip_address', lookup_expr='icontains')
    os_type = filters.ChoiceFilter(
        field_name='os_type',
        lookup_expr='exact',
        choices=ServerOSTypeChoices.choices,
    )
    status = filters.ChoiceFilter(
        field_name='status',
        lookup_expr='exact',
        choices=ServerStatusChoices.choices,
    )
    rack_location = filters.CharFilter(field_name='rack_location', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')
    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )

    class Meta:
        """元数据配置。"""

        model = LocalServer
        fields = [
            'name',
            'hostname',
            'ip_address',
            'os_type',
            'status',
            'rack_location',
            'is_active',
            'company',
        ]


class LocalVMFilter(BaseFilterSet):
    """本地虚拟主机过滤器。"""

    pk = filters.CharFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    host_server = filters.CharFilter(field_name='host_server__pk', lookup_expr='exact')
    ip_address = filters.CharFilter(field_name='ip_address', lookup_expr='icontains')
    os_type = filters.ChoiceFilter(
        field_name='os_type',
        lookup_expr='exact',
        choices=ServerOSTypeChoices.choices,
    )
    hypervisor = filters.ChoiceFilter(
        field_name='hypervisor',
        lookup_expr='exact',
        choices=HypervisorTypeChoices.choices,
    )
    status = filters.ChoiceFilter(
        field_name='status',
        lookup_expr='exact',
        choices=ServerStatusChoices.choices,
    )
    is_active = filters.BooleanFilter(field_name='is_active')
    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )

    class Meta:
        """元数据配置。"""

        model = LocalVM
        fields = [
            'name',
            'host_server',
            'ip_address',
            'os_type',
            'hypervisor',
            'status',
            'is_active',
            'company',
        ]


class DnsRecordFilter(BaseFilterSet):
    """DNS 解析记录过滤器。"""

    pk = filters.CharFilter(field_name='id')
    domain = filters.CharFilter(field_name='domain__pk', lookup_expr='exact')
    record_type = filters.ChoiceFilter(
        field_name='record_type',
        lookup_expr='exact',
        choices=DnsRecordTypeChoices.choices,
    )
    host = filters.CharFilter(field_name='host', lookup_expr='icontains')
    value = filters.CharFilter(field_name='value', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        """元数据配置。"""

        model = DnsRecord
        fields = ['domain', 'record_type', 'host', 'value', 'is_active']
