"""域名管理应用的视图集。"""

import io
import zipfile
from typing import Any

from django.db.models import Count, Prefetch
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.core.modelset import BaseModelSet, ImportExportDataAction, OnlyListModelSet
from apps.common.core.response import ApiResponse
from apps.domain.filters import (
    DnsRecordFilter,
    DomainFilter,
    FilingFilter,
    SslCertificateFilter,
)
from apps.domain.models import (
    DnsRecord,
    Domain,
    Filing,
    SslCertificate,
)
from apps.domain.serializers import (
    DnsRecordSerializer,
    DomainSerializer,
    FilingSerializer,
    SslCertificateSerializer,
)


class DomainViewSet(BaseModelSet, ImportExportDataAction):
    """域名资产管理，支持导入导出。"""

    queryset = Domain.objects.select_related('platform', 'company').annotate(
        dns_count=Count('dns_records'),
    )
    serializer_class = DomainSerializer
    filterset_class = DomainFilter
    ordering_fields = ['created_time', 'domain_name', 'expire_time', 'dns_count']


class DnsRecordViewSet(BaseModelSet, ImportExportDataAction):
    """DNS 解析记录管理，支持导入导出。"""

    queryset = DnsRecord.objects.select_related('domain')
    serializer_class = DnsRecordSerializer
    filterset_class = DnsRecordFilter
    ordering_fields = ['created_time', 'record_type', 'host']


class FilingViewSet(BaseModelSet, ImportExportDataAction):
    """备案信息管理，同时管理 ICP 备案与公安备案，支持 ICP 预检测。"""

    # 预加载关联域名的 www 解析记录到 www_dns_records 属性，避免序列化时 N+1 查询
    queryset = Filing.objects.select_related('domain', 'company').prefetch_related(
        Prefetch(
            'domain__dns_records',
            queryset=DnsRecord.objects.filter(host='www'),
            to_attr='www_dns_records',
        )
    )
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
        from apps.domain.filing_checker import apply_precheck_result, run_icp_precheck

        filing = self.get_object()
        result = run_icp_precheck(filing.domain.domain_name)

        # 回写检测结果（公共方法统一处理元信息 + ICP/公安状态联动 + SSL 同步）
        update_fields = apply_precheck_result(filing, result, check_time=timezone.now())
        filing.save(update_fields=update_fields)

        # 同步更新 Domain（SSL 启用状态 + 到期时间 + 证书关联）
        if result.get('has_www_record'):
            domain_fields = ['is_ssl_enabled']
            if result.get('ssl_certificate'):
                domain_fields.extend(['ssl_expire_time', 'ssl_certificate'])
            filing.domain.save(update_fields=domain_fields)

        return ApiResponse(data=result)

    @action(detail=False, methods=['post'], url_path='pre-check-batch')
    def pre_check_batch(self, request: Any) -> Response:
        """批量触发 ICP 备案预检测（异步执行）。

        请求体可选 filings 字段（PK 列表）：
        - 传入时仅检测指定的记录
        - 不传时自动筛选所有「未检测」「疑似未悬挂」「检测失败」状态的记录

        通过 Celery 异步执行，使用 ThreadPoolExecutor 控制并发（最多 5 个同时请求），
        避免大量域名同时检测导致带宽暴增。

        POST /api/domain/filing/pre-check-batch/
        Body: {"filings": ["pk1", "pk2"]}  （可选）

        Returns:
            包含 task_id 的 ApiResponse。
        """
        from apps.domain.tasks import batch_icp_precheck_task

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


class SslCertificateViewSet(OnlyListModelSet, ImportExportDataAction):
    """SSL 证书管理（只读列表 + 详情 + 导出），数据由备案预检测自动填充。

    支持导出为 NGINX / Apache / Caddy 格式的证书文件包（zip）。
    """

    queryset = SslCertificate.objects.prefetch_related('domains')
    serializer_class = SslCertificateSerializer
    filterset_class = SslCertificateFilter
    ordering_fields = ['not_after', 'not_before', 'created_time', 'domain__domain_name']

    @action(detail=True, methods=['get'], url_path='export-cert')
    def export_cert(self, request: Any, pk: str) -> HttpResponse:
        """导出 SSL 证书文件包（zip），支持 NGINX / Apache / Caddy 三种格式。

        - NGINX: fullchain.pem（终端证书+中间证书链）+ privkey.pem
        - Apache: cert.pem（终端证书）+ chain.pem（中间证书链）+ privkey.pem
        - Caddy:  fullchain.pem + privkey.pem（同 NGINX）

        GET /api/domain/ssl-certificate/{pk}/export-cert?type=nginx

        注意：查询参数使用 ``type`` 而非 ``format``，因为 DRF 默认将 ``format``
        查询参数用于内容协商（``URL_FORMAT_OVERRIDE``），若使用 ``format=nginx``
        会触发 ``select_renderer → filter_renderers`` 找不到匹配渲染器而抛出
        ``Http404``，最终被全局异常处理器转换为 400 响应。
        """
        cert = self.get_object()

        # 确定导出格式
        fmt = request.query_params.get('type', 'nginx').lower()
        if fmt not in ('nginx', 'apache', 'caddy'):
            fmt = 'nginx'

        # 获取证书内容
        certificate_pem = cert.certificate_pem or ''
        intermediate_pem = cert.intermediate_pem or ''
        private_key_pem = cert.private_key_pem or ''

        # 获取关联域名作为文件名前缀
        domain_name = cert.domains.first()
        file_prefix = domain_name.domain_name if domain_name else f'cert-{pk}'

        # 构建 zip 文件
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            if fmt in ('nginx', 'caddy'):
                # NGINX / Caddy: fullchain.pem = 终端证书 + 中间证书链
                fullchain = certificate_pem
                if intermediate_pem:
                    if not fullchain.endswith('\n'):
                        fullchain += '\n'
                    fullchain += intermediate_pem
                zf.writestr(f'{file_prefix}_fullchain.pem', fullchain)
                if private_key_pem:
                    zf.writestr(f'{file_prefix}_privkey.pem', private_key_pem)
            elif fmt == 'apache':
                # Apache: 分开存放终端证书和中间证书链
                zf.writestr(f'{file_prefix}_cert.pem', certificate_pem)
                if intermediate_pem:
                    zf.writestr(f'{file_prefix}_chain.pem', intermediate_pem)
                if private_key_pem:
                    zf.writestr(f'{file_prefix}_privkey.pem', private_key_pem)

        zip_buffer.seek(0)

        # 构建响应
        response: HttpResponse = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{file_prefix}_{fmt}.zip"'
        return response
