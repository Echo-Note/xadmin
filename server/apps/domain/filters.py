"""域名管理应用的过滤器定义。

从 apps.asset.filters 迁移而来，仅保留域名相关过滤器。
"""

from django.db.models import QuerySet
from django_filters import rest_framework as filters

from apps.cloud_platform.models import CloudPlatform
from apps.common.core.filter import BaseFilterSet
from apps.company.models import Company
from apps.domain.choices import (
    DnsRecordTypeChoices,
    DomainStatusChoices,
    IcpCheckStatusChoices,
    IcpFilingStatusChoices,
)
from apps.domain.models import DnsRecord, Domain, Filing, SslCertificate


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
    is_active = filters.BooleanFilter(field_name='is_active')
    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )
    expire_time = filters.DateFromToRangeFilter(field_name='expire_time')
    is_icp_filed = filters.BooleanFilter(
        field_name='filing__icp_number',
        method='filter_related_filing',
        label='ICP 备案',
    )
    is_ps_filed = filters.BooleanFilter(
        field_name='filing__ps_filing_number',
        method='filter_related_filing',
        label='公安备案',
    )

    def filter_related_filing(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """按 Filing 关联表备案号是否为空过滤。True=已备案（非空）。"""
        if value:
            return queryset.exclude(**{name: ''}).filter(**{f'{name}__isnull': False})
        return queryset.filter(**{name: ''}) | queryset.filter(**{f'{name}__isnull': True})

    class Meta:
        """元数据配置。"""

        model = Domain
        fields = [
            'domain_name',
            'registrar',
            'platform',
            'status',
            'is_ssl_enabled',
            'is_active',
            'company',
            'expire_time',
            'is_icp_filed',
            'is_ps_filed',
        ]


class FilingFilter(BaseFilterSet):
    """备案信息过滤器。"""

    pk = filters.CharFilter(field_name='id')
    domain = filters.ModelChoiceFilter(
        field_name='domain',
        lookup_expr='exact',
        queryset=Domain.objects.filter(is_active=True),
        label='关联域名',
    )
    icp_status = filters.ChoiceFilter(
        field_name='icp_status',
        lookup_expr='exact',
        choices=IcpFilingStatusChoices.choices,
        label='ICP 备案状态',
    )
    icp_check_status = filters.ChoiceFilter(
        field_name='icp_check_status',
        lookup_expr='exact',
        choices=IcpCheckStatusChoices.choices,
        label='ICP 预检测状态',
    )
    ps_status = filters.ChoiceFilter(
        field_name='ps_status',
        lookup_expr='exact',
        choices=IcpFilingStatusChoices.choices,
        label='公安备案状态',
    )
    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )

    class Meta:
        """元数据配置。"""

        model = Filing
        fields = ['domain', 'icp_status', 'icp_check_status', 'ps_status', 'company']


class SslCertificateFilter(BaseFilterSet):
    """SSL 证书过滤器。"""

    pk = filters.CharFilter(field_name='id')
    is_valid = filters.BooleanFilter(field_name='is_valid')
    issuer_cn = filters.CharFilter(field_name='issuer_cn', lookup_expr='icontains')
    subject_cn = filters.CharFilter(field_name='subject_cn', lookup_expr='icontains')
    not_after = filters.DateFromToRangeFilter(field_name='not_after')
    domain_name = filters.CharFilter(
        field_name='domains__domain_name',
        lookup_expr='icontains',
        label='关联域名',
    )

    class Meta:
        """元数据配置。"""

        model = SslCertificate
        fields = ['is_valid', 'issuer_cn', 'subject_cn', 'not_after', 'domain_name']


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
