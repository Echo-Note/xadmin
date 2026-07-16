"""资产关联图谱 — 构建域名、DNS记录、服务器、云平台、公司之间的关联关系。"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.asset.models import CloudServer, DnsRecord, Domain, LocalServer, LocalVM
from apps.cloud_platform.models import CloudPlatform
from apps.common.core.response import ApiResponse
from apps.company.models import Company


@dataclass
class RelationNode:
    """图谱节点。"""

    id: str
    type: str  # domain/dns_record/server/local_server/local_vm/platform/company
    label: str
    pk: str = ''
    detail_url: str = ''
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationEdge:
    """图谱边。"""

    source: str
    target: str
    label: str = ''


class RelationGraphView(APIView):
    """资产关联图谱 API。

    GET /api/asset/relation-graph/?domain=<pk>

    返回域名及其解析记录、关联服务器、云平台、公司主体的图谱数据。
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):  # noqa: ANN001, ANN201
        """构建并返回图谱数据。

        Query params:
            domain: 域名 PK（必填）。
        """
        domain_pk = request.query_params.get('domain', '')
        if not domain_pk:
            return ApiResponse(
                code=400,
                detail='缺少 domain 参数',
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            domain = Domain.objects.select_related('platform', 'company').get(pk=domain_pk)
        except Domain.DoesNotExist:
            return ApiResponse(
                code=404,
                detail='域名不存在',
                status=status.HTTP_404_NOT_FOUND,
            )

        nodes: list[dict] = []
        edges: list[dict] = []
        seen_ids: set[str] = set()

        def add_node(n: RelationNode) -> None:
            if n.id not in seen_ids:
                seen_ids.add(n.id)
                nodes.append(
                    {
                        'id': n.id,
                        'type': n.type,
                        'label': n.label,
                        'pk': n.pk,
                        'detail_url': n.detail_url,
                        **n.extra,
                    }
                )

        def add_edge(e: RelationEdge) -> None:
            edges.append(
                {
                    'source': e.source,
                    'target': e.target,
                    'label': e.label,
                }
            )

        # ---- 1. 域名节点 ----
        domain_node_id = f'domain-{domain.pk}'
        add_node(
            RelationNode(
                id=domain_node_id,
                type='domain',
                label=domain.domain_name,
                pk=str(domain.pk),
                detail_url=f'/api/asset/domain/{domain.pk}/',
                extra={'registrar': domain.registrar or '', 'status': get_domain_status(domain)},
            )
        )

        # ---- 2. 域名 → 公司 ----
        if domain.company_id:
            company_id = f'company-{domain.company_id}'
            add_node(_build_company_node(domain.company_id))
            add_edge(RelationEdge(domain_node_id, company_id, '归属主体'))

        # ---- 3. 域名 → 云平台 ----
        if domain.platform_id:
            platform_id = f'platform-{domain.platform_id}'
            add_node(_build_platform_node(domain.platform_id))
            add_edge(RelationEdge(domain_node_id, platform_id, '解析平台'))

        # ---- 4. DNS 解析记录 ----
        dns_records = DnsRecord.objects.filter(domain_id=domain.pk).select_related('domain')
        all_record_ips: dict[str, str] = {}  # ip → dns_node_id 映射

        for rec in dns_records:
            dns_node_id = f'dns-{rec.pk}'
            # 显示完整域名：@ → 域名本身，www → www.example.com
            full_domain = f'{rec.host}.{domain.domain_name}' if rec.host and rec.host != '@' else domain.domain_name
            add_node(
                RelationNode(
                    id=dns_node_id,
                    type='dns_record',
                    label=f'{rec.record_type} {full_domain}',
                    pk=str(rec.pk),
                    detail_url=f'/api/asset/dns-record/{rec.pk}/',
                    extra={
                        'value': rec.value,
                        'ttl': rec.ttl,
                        'record_type': rec.record_type,
                        'host': rec.host,
                    },
                )
            )
            add_edge(RelationEdge(domain_node_id, dns_node_id, '解析记录'))

            # 提取 IP 类型的记录值
            ip = extract_ip(rec.value)
            if ip:
                all_record_ips[ip] = dns_node_id

        # ---- 5. 按 IP 匹配服务器 ----
        if all_record_ips:
            ip_list = list(all_record_ips.keys())

            # 云服务器
            cloud_servers = CloudServer.objects.filter(
                Q(public_ip__in=ip_list) | Q(private_ip__in=ip_list),
            ).select_related('platform', 'company')
            for srv in cloud_servers:
                srv_ip = srv.public_ip or srv.private_ip or ''
                if not srv_ip:
                    continue
                # 找到匹配的 DNS 记录
                for ip, dns_id in all_record_ips.items():
                    if ip in (srv.public_ip or '', srv.private_ip or ''):
                        srv_id = f'cloud-server-{srv.pk}'
                        add_node(
                            RelationNode(
                                id=srv_id,
                                type='cloud_server',
                                label=srv.name,
                                pk=str(srv.pk),
                                detail_url=f'/api/asset/cloud-server/{srv.pk}/',
                                extra={
                                    'ip': srv_ip,
                                    'os': srv.os_type,
                                    'cpu': srv.cpu,
                                    'status': srv.status,
                                },
                            )
                        )
                        add_edge(RelationEdge(dns_id, srv_id, f'IP={ip}'))

                        # 服务器 → 平台
                        if srv.platform_id:
                            pid = f'platform-{srv.platform_id}'
                            add_node(_build_platform_node(srv.platform_id))
                            add_edge(RelationEdge(srv_id, pid, '归属平台'))

                        # 服务器 → 公司
                        if srv.company_id:
                            cid = f'company-{srv.company_id}'
                            add_node(_build_company_node(srv.company_id))
                            add_edge(RelationEdge(srv_id, cid, '归属主体'))

            # 本地物理服务器
            local_servers = LocalServer.objects.filter(
                ip_address__in=ip_list,
            ).select_related('company')
            for srv in local_servers:
                for ip, dns_id in all_record_ips.items():
                    if ip == srv.ip_address:
                        srv_id = f'local-server-{srv.pk}'
                        add_node(
                            RelationNode(
                                id=srv_id,
                                type='local_server',
                                label=srv.name,
                                pk=str(srv.pk),
                                detail_url=f'/api/asset/local-server/{srv.pk}/',
                                extra={
                                    'ip': srv.ip_address,
                                    'os': srv.os_type,
                                    'cpu': srv.cpu_total_threads or 0,
                                    'status': srv.status,
                                },
                            )
                        )
                        add_edge(RelationEdge(dns_id, srv_id, f'IP={ip}'))

                        if srv.company_id:
                            cid = f'company-{srv.company_id}'
                            add_node(_build_company_node(srv.company_id))
                            add_edge(RelationEdge(srv_id, cid, '归属主体'))

            # 本地虚拟机
            local_vms = LocalVM.objects.filter(
                ip_address__in=ip_list,
            ).select_related('company')
            for vm in local_vms:
                for ip, dns_id in all_record_ips.items():
                    if ip == vm.ip_address:
                        vm_id = f'local-vm-{vm.pk}'
                        add_node(
                            RelationNode(
                                id=vm_id,
                                type='local_vm',
                                label=vm.name,
                                pk=str(vm.pk),
                                detail_url=f'/api/asset/local-vm/{vm.pk}/',
                                extra={
                                    'ip': vm.ip_address,
                                    'os': vm.os_type,
                                    'cpu': vm.cpu,
                                    'status': vm.status,
                                },
                            )
                        )
                        add_edge(RelationEdge(dns_id, vm_id, f'IP={ip}'))

                        if vm.company_id:
                            cid = f'company-{vm.company_id}'
                            add_node(_build_company_node(vm.company_id))
                            add_edge(RelationEdge(vm_id, cid, '归属主体'))

        return ApiResponse(data={'nodes': nodes, 'edges': edges})


# ---- 辅助函数 ----


def _build_company_node(company_id: Any) -> RelationNode:
    """构建公司节点（带缓存查询）。"""
    company = Company.objects.only('pk', 'name', 'short_name').get(pk=company_id)
    short = company.short_name or company.name
    return RelationNode(
        id=f'company-{company_id}',
        type='company',
        label=short,
        pk=str(company_id),
        detail_url=f'/api/company/company/{company_id}/',
        extra={'full_name': company.name},
    )


def _build_platform_node(platform_id: Any) -> RelationNode:
    """构建云平台节点（带缓存查询）。"""
    platform = CloudPlatform.objects.only('pk', 'name', 'platform_type').get(pk=platform_id)
    pt = platform.platform_type
    type_label = pt.label if hasattr(pt, 'label') else str(pt)
    return RelationNode(
        id=f'platform-{platform_id}',
        type='platform',
        label=platform.name,
        pk=str(platform_id),
        detail_url=f'/api/cloud/platform/{platform_id}/',
        extra={'platform_type': type_label},
    )


def get_domain_status(domain: Domain) -> str:
    """提取域名状态的 label。"""
    st = domain.status
    if hasattr(st, 'label'):
        return st.label
    return str(st) if st else ''


def extract_ip(value: str) -> str | None:
    """从 DNS 记录值中提取合法 IPv4 地址。

    Args:
        value: DNS 记录值。

    Returns:
        提取到的 IP 字符串，不合法则返回 None。
    """
    if not value:
        return None
    value = value.strip()
    try:
        ipaddress.IPv4Address(value)
        # 排除明显的非服务器 IP
        if value.startswith('127.') or value.startswith('0.'):
            return None
        return value
    except (ipaddress.AddressValueError, ValueError):
        return None
