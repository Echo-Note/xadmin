"""资产管理应用的视图集。"""

from apps.asset.filters import (
    CloudServerFilter,
    DnsRecordFilter,
    DomainFilter,
    LocalServerFilter,
    LocalVMFilter,
)
from apps.asset.models import CloudServer, DnsRecord, Domain, LocalServer, LocalVM
from apps.asset.serializers import (
    CloudServerSerializer,
    DnsRecordSerializer,
    DomainSerializer,
    LocalServerSerializer,
    LocalVMSerializer,
)
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction


class CloudServerViewSet(BaseModelSet, ImportExportDataAction):
    """云服务器资产管理，支持导入导出。"""

    queryset = CloudServer.objects.select_related('platform', 'company')
    serializer_class = CloudServerSerializer
    filterset_class = CloudServerFilter
    ordering_fields = ['created_time', 'name', 'cpu', 'memory']


class DomainViewSet(BaseModelSet, ImportExportDataAction):
    """域名资产管理，支持导入导出。"""

    queryset = Domain.objects.select_related('platform', 'company')
    serializer_class = DomainSerializer
    filterset_class = DomainFilter
    ordering_fields = ['created_time', 'domain_name', 'expire_time']


class LocalServerViewSet(BaseModelSet, ImportExportDataAction):
    """本地物理服务器管理，支持导入导出。"""

    queryset = LocalServer.objects.select_related('company')
    serializer_class = LocalServerSerializer
    filterset_class = LocalServerFilter
    ordering_fields = ['created_time', 'name', 'memory']


class LocalVMViewSet(BaseModelSet, ImportExportDataAction):
    """本地虚拟主机管理，支持导入导出。"""

    queryset = LocalVM.objects.select_related('host_server', 'company')
    serializer_class = LocalVMSerializer
    filterset_class = LocalVMFilter
    ordering_fields = ['created_time', 'name', 'cpu']


class DnsRecordViewSet(BaseModelSet, ImportExportDataAction):
    """DNS 解析记录管理，支持导入导出。"""

    queryset = DnsRecord.objects.select_related('domain')
    serializer_class = DnsRecordSerializer
    filterset_class = DnsRecordFilter
    ordering_fields = ['created_time', 'record_type', 'host']
