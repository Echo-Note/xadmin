"""云平台管理应用的过滤器定义。"""

from django_filters import rest_framework as filters

from apps.cloud_platform.choices import (
    AgentStatusChoices,
    CredentialTypeChoices,
    PlatformTypeChoices,
    SyncResourceTypeChoices,
    SyncStatusChoices,
    SyncTriggerTypeChoices,
)
from apps.cloud_platform.models import CloudPlatform, Credential, SyncAgentLog, SyncRecord
from apps.common.core.filter import BaseFilterSet
from apps.company.models import Company


class CloudPlatformFilter(BaseFilterSet):
    """云平台实例过滤器。"""

    pk = filters.CharFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    platform_type = filters.ChoiceFilter(
        field_name='platform_type',
        lookup_expr='exact',
        choices=PlatformTypeChoices.choices,
        label='平台类型',
    )
    company = filters.ModelChoiceFilter(
        field_name='company',
        lookup_expr='exact',
        queryset=Company.objects.filter(is_active=True),
    )
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        """过滤器元数据配置。"""

        model = CloudPlatform
        fields = ['name', 'platform_type', 'company', 'is_active']


class CredentialFilter(BaseFilterSet):
    """凭据过滤器。"""

    pk = filters.CharFilter(field_name='id')
    platform = filters.CharFilter(field_name='platform__pk', lookup_expr='exact')
    credential_type = filters.ChoiceFilter(
        field_name='credential_type',
        lookup_expr='exact',
        choices=CredentialTypeChoices.choices,
    )
    credential_name = filters.CharFilter(field_name='credential_name', lookup_expr='icontains')
    username = filters.CharFilter(field_name='username', lookup_expr='icontains')
    email = filters.CharFilter(field_name='email', lookup_expr='icontains')
    is_active = filters.BooleanFilter(field_name='is_active')

    class Meta:
        """过滤器元数据配置。"""

        model = Credential
        fields = ['platform', 'credential_type', 'credential_name', 'username', 'email', 'is_active']


class SyncRecordFilter(BaseFilterSet):
    """同步记录过滤器。"""

    pk = filters.CharFilter(field_name='id')
    platform = filters.ModelChoiceFilter(
        field_name='platform',
        lookup_expr='exact',
        queryset=CloudPlatform.objects.filter(is_active=True),
    )
    status = filters.ChoiceFilter(
        field_name='status',
        choices=SyncStatusChoices.choices,
        label='同步状态',
    )
    sync_type = filters.ChoiceFilter(
        field_name='sync_type',
        choices=SyncTriggerTypeChoices.choices,
        label='触发类型',
    )

    class Meta:
        """过滤器元数据配置。"""

        model = SyncRecord
        fields = ['platform', 'sync_type', 'status']


class SyncAgentLogFilter(BaseFilterSet):
    """同步Agent日志过滤器。"""

    pk = filters.CharFilter(field_name='id')
    sync_record = filters.CharFilter(field_name='sync_record__pk', lookup_expr='exact')
    agent_name = filters.CharFilter(field_name='agent_name', lookup_expr='icontains')
    resource_type = filters.ChoiceFilter(
        field_name='resource_type',
        choices=SyncResourceTypeChoices.choices,
        label='资源类型',
    )
    status = filters.ChoiceFilter(
        field_name='status',
        choices=AgentStatusChoices.choices,
        label='执行状态',
    )

    class Meta:
        """过滤器元数据配置。"""

        model = SyncAgentLog
        fields = ['sync_record', 'agent_name', 'resource_type', 'status']
