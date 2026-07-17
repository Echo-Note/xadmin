"""资产管理应用的视图集。"""

from typing import Any

from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.asset.filters import (
    CloudServerFilter,
    DnsRecordFilter,
    DomainFilter,
    FilingFilter,
    LocalServerFilter,
    LocalVMFilter,
)
from apps.asset.models import CloudServer, DnsRecord, Domain, Filing, LocalServer, LocalVM
from apps.asset.serializers import (
    CloudServerSerializer,
    DnsRecordSerializer,
    DomainSerializer,
    FilingSerializer,
    LocalServerSerializer,
    LocalVMSerializer,
)
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.response import ApiResponse


class CloudServerViewSet(BaseModelSet, ImportExportDataAction):
    """云服务器资产管理，支持导入导出。"""

    queryset = CloudServer.objects.select_related('platform', 'company')
    serializer_class = CloudServerSerializer
    filterset_class = CloudServerFilter
    ordering_fields = ['created_time', 'name', 'cpu', 'memory']


class DomainViewSet(BaseModelSet, ImportExportDataAction):
    """域名资产管理，支持导入导出。"""

    queryset = Domain.objects.select_related('platform', 'company').annotate(
        dns_count=Count('dns_records'),
    )
    serializer_class = DomainSerializer
    filterset_class = DomainFilter
    ordering_fields = ['created_time', 'domain_name', 'expire_time', 'dns_count']


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


class FilingViewSet(BaseModelSet, ImportExportDataAction):
    """备案信息管理，同时管理 ICP 备案与公安备案，支持 ICP 预检测。"""

    queryset = Filing.objects.select_related('domain', 'company')
    serializer_class = FilingSerializer
    filterset_class = FilingFilter
    ordering_fields = ['created_time', 'domain__domain_name']

    @action(detail=True, methods=['post'], url_path='pre-check')
    def pre_check(self, request: Any) -> Response:
        """对指定的 Filing 记录执行 ICP 备案悬挂预检测。

        检测流程：
        1. 检查域名是否存在 www 子域名 DNS 解析记录
        2. 若存在 www 记录，通过 HTTPS 访问首页
        3. 提取页脚区域文本，匹配 ICP 备案号
        4. 更新 Filing 记录的预检测相关字段

        Returns:
            包含检测结果的 ApiResponse。
        """
        from apps.asset.filing_checker import run_icp_precheck

        filing = self.get_object()
        result = run_icp_precheck(filing.domain.domain_name)

        # 回写检测元信息
        filing.icp_has_www_record = result['has_www_record']
        filing.icp_check_status = result['check_status']
        filing.icp_check_conclusion = result['conclusion']
        filing.icp_check_time = timezone.now()
        if result.get('footer_content') is not None:
            filing.icp_footer_content = result['footer_content']

        # 联动回写 ICP 备案号和状态
        icp_nums = result.get('detected_icp_numbers', [])
        if icp_nums:
            filing.icp_number = icp_nums[0]
            filing.icp_status = 'filed'
        elif result['check_status'] == 'suspected_missing':
            filing.icp_status = 'pending_confirm'

        # 联动回写公安备案号和状态
        ps_nums = result.get('detected_ps_numbers', [])
        if ps_nums:
            filing.ps_filing_number = ps_nums[0]
            filing.ps_status = 'filed'
        elif result['check_status'] == 'suspected_missing':
            filing.ps_status = 'pending_confirm'

        filing.save(
            update_fields=[
                'icp_has_www_record',
                'icp_check_status',
                'icp_check_conclusion',
                'icp_check_time',
                'icp_footer_content',
                'icp_number',
                'icp_status',
                'ps_filing_number',
                'ps_status',
            ]
        )

        # 同步更新 Domain 的 SSL 启用状态
        if result.get('has_www_record'):
            filing.domain.is_ssl_enabled = result.get('used_https', False)
            filing.domain.save(update_fields=['is_ssl_enabled'])

        return ApiResponse(data=result)

    @action(detail=False, methods=['post'], url_path='pre-check-batch')
    def pre_check_batch(self, request: Any) -> Response:
        """批量触发 ICP 备案预检测（异步执行）。

        请求体可选 filings 字段（PK 列表）：
        - 传入时仅检测指定的记录
        - 不传时自动筛选所有「未检测」「疑似未悬挂」「检测失败」状态的记录

        通过 Celery 异步执行，使用 ThreadPoolExecutor 控制并发（最多 5 个同时请求），
        避免大量域名同时检测导致带宽暴增。

        POST /api/asset/filing/pre-check-batch/
        Body: {"filings": ["pk1", "pk2"]}  （可选）

        Returns:
            包含 task_id 的 ApiResponse。
        """
        from apps.asset.tasks import batch_icp_precheck_task

        filings = request.data.get('filings')
        pks: list[str] | None = None
        if isinstance(filings, list) and len(filings) > 0:
            pks = [str(pk) for pk in filings]

        task = batch_icp_precheck_task.delay(pks=pks)

        return ApiResponse(
            data={
                'task_id': task.id,
                'message': '批量预检测任务已提交，请在后台查看执行结果。',
                'filings_count': len(pks) if pks else 'auto',
            }
        )
