"""腾讯云同步器 — CVM/域名/DNSPod/余额。"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from apps.cloud_platform.sync.base import BaseCloudSyncer
from apps.cloud_platform.sync.registry import register_syncer
from apps.cloud_platform.sync.schemas import (
    BalanceSyncData,
    DnsRecordSyncData,
    DomainSyncData,
    ServerSyncData,
)

logger = logging.getLogger(__name__)

# SDK optional import
try:
    from tencentcloud.billing.v20180709 import billing_client
    from tencentcloud.billing.v20180709 import models as billing_models
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.cvm.v20170312 import cvm_client
    from tencentcloud.cvm.v20170312 import models as cvm_models
    from tencentcloud.dnspod.v20210323 import dnspod_client
    from tencentcloud.dnspod.v20210323 import models as dnspod_models
    from tencentcloud.domain.v20180808 import domain_client
    from tencentcloud.domain.v20180808 import models as domain_models

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning('腾讯云 SDK 未安装: pip install tencentcloud-sdk-python')

PAGE_SIZE = 50


@register_syncer
class TencentCloudSyncer(BaseCloudSyncer):
    """腾讯云资源同步器 — 仅负责 API 数据拉取和格式转换。

    支持资源类型：
    - server: CVM 云服务器
    - domain: 域名注册
    - dns_record: DNSPod 解析记录
    - balance: 账户余额
    """

    PLATFORM_TYPE = 'tencent'
    PLATFORM_NAMES = ['腾讯云', 'tencent', 'tencentcloud']
    SUPPORTED_RESOURCES = {'server', 'domain', 'dns_record', 'balance'}

    def __init__(self, cloud_platform) -> None:  # noqa: ANN001
        """初始化腾讯云同步器。

        Args:
            cloud_platform: CloudPlatform 模型实例。
        """
        super().__init__(cloud_platform)
        self._ak = ''
        self._sk = ''

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _setup(self) -> bool:
        """初始化 AK/SK 配置。

        Returns:
            True 表示配置有效，可以发起 API 调用。
        """
        if not SDK_AVAILABLE:
            return False
        creds = self.credentials
        self._ak = creds.get('access_key', '')
        self._sk = creds.get('access_secret', '')
        return bool(self._ak)

    def _build_cred(self):  # noqa: ANN202
        """构建腾讯云 Credential 对象。"""
        return credential.Credential(self._ak, self._sk)

    def _build_client(self, client_cls, region: str = 'ap-guangzhou', endpoint: str = ''):  # noqa: ANN001, ANN202
        """构建腾讯云 API 客户端。

        Args:
            client_cls: 客户端类（如 CvmClient）。
            region: 区域标识。
            endpoint: API 端点域名。

        Returns:
            配置好的客户端实例。
        """
        cred = self._build_cred()
        hp = HttpProfile()
        if endpoint:
            hp.endpoint = endpoint
        cp = ClientProfile()
        cp.httpProfile = hp
        return client_cls(cred, region, cp)

    # ------------------------------------------------------------------
    # 云服务器 (CVM)
    # ------------------------------------------------------------------

    def _fetch_servers(self) -> list[ServerSyncData]:
        """获取所有区域的 CVM 实例列表（幂等：同参数多次调用返回相同数据）。"""
        if not self._setup():
            return []
        results: list[ServerSyncData] = []
        status_map = {
            'RUNNING': 'running',
            'STOPPED': 'stopped',
            'STARTING': 'starting',
            'STOPPING': 'stopping',
            'REBOOTING': 'rebooting',
            'PENDING': 'pending',
            'TERMINATED': 'terminated',
        }
        for region in self.regions:
            try:
                client = self._build_client(cvm_client.CvmClient, region)
                offset = 0
                while True:
                    req = cvm_models.DescribeInstancesRequest()
                    req.Offset = offset
                    req.Limit = PAGE_SIZE
                    resp = client.DescribeInstances(req)
                    if not resp.InstanceSet:
                        break
                    for inst in resp.InstanceSet:
                        expire = None
                        if inst.ExpiredTime:
                            try:
                                expire = date.fromisoformat(inst.ExpiredTime[:10])
                            except (ValueError, TypeError):
                                pass
                        disk = None
                        if inst.SystemDisk and inst.SystemDisk.DiskSize:
                            try:
                                disk = float(inst.SystemDisk.DiskSize)
                            except (ValueError, TypeError):
                                pass
                        tags: dict[str, str] = {}
                        if inst.Tags:
                            for t in inst.Tags:
                                if t.Key:
                                    tags[t.Key] = t.Value or ''
                        results.append(
                            ServerSyncData(
                                hostname=inst.InstanceName or '',
                                instance_id=inst.InstanceId or '',
                                status=status_map.get(inst.InstanceState or '', 'unknown'),
                                os=inst.OsName or '',
                                os_version=inst.OsName or '',
                                cpu_cores=int(inst.CPU) if inst.CPU else None,
                                memory_gb=float(inst.Memory) if inst.Memory else None,
                                disk_gb=disk,
                                public_ips=list(inst.PublicIpAddresses or []),
                                private_ips=list(inst.PrivateIpAddresses or []),
                                expire_date=expire,
                                region=region,
                                tags=tags,
                            )
                        )
                    if offset + PAGE_SIZE >= (resp.TotalCount or 0):
                        break
                    offset += PAGE_SIZE
            except Exception:
                logger.exception('区域[%s] CVM 实例拉取失败', region)
        return results

    # ------------------------------------------------------------------
    # 域名
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_get(obj, attr: str, default: str = '') -> str:  # noqa: ANN001
        """兼容 SDK 模型对象与 dict 两种返回格式的安全取值。

        Args:
            obj: SDK 返回的模型对象或 dict。
            attr: 属性/键名。
            default: 取不到时的默认值。

        Returns:
            字段值或默认值。
        """
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _fetch_info_templates(self) -> dict[str, dict]:
        """获取腾讯云域名信息模板列表，缓存在内存中供域名详情关联。

        Returns:
            {TemplateId: {credit_code, company_name, cert_type, contact_name,
                          contact_email, registrant_type}} 字典。
        """
        if not self._setup():
            return {}

        templates: dict[str, dict] = {}
        try:
            client = self._build_client(
                domain_client.DomainClient,
                endpoint='domain.tencentcloudapi.com',
            )
            offset = 0
            while True:
                req = domain_models.DescribeTemplateListRequest()
                req.Offset = offset
                req.Limit = PAGE_SIZE
                resp = client.DescribeTemplateList(req)
                if not resp.TemplateSet:
                    break
                for tmpl in resp.TemplateSet:
                    tid = self._safe_get(tmpl, 'TemplateId') or ''
                    if not tid:
                        continue

                    cert_info = self._safe_get(tmpl, 'CertificateInfo', None)
                    contact_info = self._safe_get(tmpl, 'ContactInfo', None)

                    credit_code = ''
                    cert_type = ''
                    company_name = ''
                    contact_name = ''
                    contact_email = ''
                    registrant_type = ''

                    if cert_info:
                        cert_type = self._safe_get(cert_info, 'CertificateType') or ''
                        cert_code = self._safe_get(cert_info, 'CertificateCode') or ''
                        if cert_type in ('TYDMZ', 'QTTYDM', 'YYZZ'):
                            credit_code = cert_code

                    if contact_info:
                        company_name = (
                            self._safe_get(contact_info, 'OrganizationNameCN')
                            or self._safe_get(contact_info, 'OrganizationName')
                            or ''
                        )
                        contact_name = (
                            self._safe_get(contact_info, 'RegistrantNameCN')
                            or self._safe_get(contact_info, 'RegistrantName')
                            or ''
                        )
                        contact_email = self._safe_get(contact_info, 'Email') or ''
                        registrant_type = self._safe_get(contact_info, 'RegistrantType') or ''

                    templates[tid] = {
                        'credit_code': credit_code,
                        'company_name': company_name,
                        'cert_type': cert_type,
                        'contact_name': contact_name,
                        'contact_email': contact_email,
                        'registrant_type': registrant_type,
                    }

                if offset + PAGE_SIZE >= (resp.TotalCount or 0):
                    break
                offset += PAGE_SIZE
        except Exception:
            logger.exception('腾讯云信息模板列表拉取失败')

        logger.info('腾讯云信息模板: %d 个', len(templates))
        return templates

    def _fetch_domains(self) -> list[DomainSyncData]:
        """获取所有域名列表并关联信息模板中的企业主体数据（幂等）。"""
        if not self._setup():
            return []

        # Step 1: 获取信息模板缓存
        templates = self._fetch_info_templates()

        # Step 2: 获取域名名称列表
        names: list[str] = []
        try:
            client = self._build_client(
                domain_client.DomainClient,
                endpoint='domain.tencentcloudapi.com',
            )
            offset = 0
            while True:
                req = domain_models.DescribeDomainNameListRequest()
                req.Offset = offset
                req.Limit = PAGE_SIZE
                resp = client.DescribeDomainNameList(req)
                if not resp.DomainSet:
                    break
                for item in resp.DomainSet:
                    name = item.DomainName if hasattr(item, 'DomainName') else item.get('DomainName', '')
                    if name:
                        names.append(name)
                if offset + PAGE_SIZE >= (resp.TotalCount or 0):
                    break
                offset += PAGE_SIZE
        except Exception:
            logger.exception('腾讯云域名列表拉取失败')
            return []

        logger.info('腾讯云域名列表: %d 个', len(names))

        # Step 3: 逐个获取域名详情，关联模板信息
        results: list[DomainSyncData] = []
        for name in names:
            try:
                req = domain_models.DescribeDomainSimpleInfoRequest()
                req.DomainName = name
                resp = client.DescribeDomainSimpleInfo(req)
                info = resp.DomainInfo
                if not info:
                    results.append(DomainSyncData(name=name))
                    continue
                rd = None
                ed = None
                if info.CreationDate:
                    try:
                        rd = date.fromisoformat(info.CreationDate[:10])
                    except (ValueError, TypeError):
                        pass
                if info.ExpirationDate:
                    try:
                        ed = date.fromisoformat(info.ExpirationDate[:10])
                    except (ValueError, TypeError):
                        pass
                raw_status = info.DomainStatus or ''
                if isinstance(raw_status, list):
                    raw_status = raw_status[0] if raw_status else ''

                ns = getattr(info, 'NameServer', []) or []
                dns = ', '.join(ns[:2]) if isinstance(ns, list) and ns else ''

                owner = info.RegistrantNameCN or info.OrganizationNameCN or ''

                template_id = getattr(info, 'TemplateId', '') or ''
                template_info = templates.get(template_id, {})

                company = template_info.get('company_name') or info.OrganizationNameCN or info.OrganizationName or None
                credit = template_info.get('credit_code') or None
                contact_person = template_info.get('contact_name') or None
                contact_email = template_info.get('contact_email') or None

                registrant_type = template_info.get('registrant_type') or getattr(info, 'RegistrantType', '')
                company_type = None
                if registrant_type == 'E':
                    company_type = '企业'
                elif registrant_type == 'I':
                    company_type = '个人'

                results.append(
                    DomainSyncData(
                        name=name,
                        registrar_name='腾讯云',
                        register_date=rd,
                        expire_date=ed,
                        dns_provider=dns,
                        status=raw_status,
                        owner_name=owner,
                        company_name=company,
                        credit_code=credit,
                        company_type=company_type,
                        contact_person=contact_person,
                        contact_email=contact_email,
                    )
                )
            except Exception:
                logger.exception('腾讯云域名详情拉取失败: %s', name)
                results.append(DomainSyncData(name=name))
        return results

    # ------------------------------------------------------------------
    # DNS 解析记录 (DNSPod)
    # ------------------------------------------------------------------

    def _fetch_dns_records(self) -> list[DnsRecordSyncData]:
        """获取 DNSPod 所有域名的解析记录（幂等：同参数多次调用返回相同数据）。"""
        if not self._setup():
            return []
        records: list[DnsRecordSyncData] = []
        try:
            client = self._build_client(
                dnspod_client.DnspodClient,
                endpoint='dnspod.tencentcloudapi.com',
            )

            domains: list[str] = []
            try:
                offset = 0
                while True:
                    req = dnspod_models.DescribeDomainListRequest()
                    req.Offset = offset
                    req.Limit = PAGE_SIZE
                    resp = client.DescribeDomainList(req)
                    if not resp.DomainList:
                        break
                    for d in resp.DomainList:
                        if d.Name:
                            domains.append(d.Name)
                    total = resp.DomainCountInfo.DomainTotal if resp.DomainCountInfo else 0
                    if offset + PAGE_SIZE >= total:
                        break
                    offset += PAGE_SIZE
            except Exception:
                logger.exception('DNSPod 域名列表拉取失败')

            for domain_name in domains:
                try:
                    offset = 0
                    while True:
                        req = dnspod_models.DescribeRecordListRequest()
                        req.Domain = domain_name
                        req.Offset = offset
                        req.Limit = PAGE_SIZE
                        resp = client.DescribeRecordList(req)
                        if not resp.RecordList:
                            break
                        for rec in resp.RecordList:
                            records.append(
                                DnsRecordSyncData(
                                    domain_name=domain_name,
                                    record_type=rec.Type or 'A',
                                    host_record=rec.Name or '@',
                                    record_value=rec.Value or '',
                                    ttl=rec.TTL or 600,
                                    line=rec.Line or '默认',
                                )
                            )
                        total = resp.RecordCountInfo.TotalCount if resp.RecordCountInfo else 0
                        if offset + PAGE_SIZE >= total:
                            break
                        offset += PAGE_SIZE
                except Exception:
                    logger.exception('DNSPod 解析记录拉取失败: %s', domain_name)
        except Exception:
            logger.exception('DNSPod 客户端初始化失败')
        return records

    # ------------------------------------------------------------------
    # 账户余额
    # ------------------------------------------------------------------

    def _fetch_balance(self) -> BalanceSyncData | None:
        """获取账户余额（幂等：同参数多次调用返回相同数据）。"""
        if not self._setup():
            return None
        try:
            client = self._build_client(
                billing_client.BillingClient,
                endpoint='billing.tencentcloudapi.com',
            )
            req = billing_models.DescribeAccountBalanceRequest()
            resp = client.DescribeAccountBalance(req)
            total = Decimal(str(resp.RealBalance or 0)) / Decimal('100')
            return BalanceSyncData(
                total_balance=total,
                currency='CNY',
                recorded_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception('腾讯云账户余额拉取失败')
            return None
