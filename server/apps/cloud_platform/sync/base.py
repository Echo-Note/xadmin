"""云平台资源同步抽象基类。

定义统一的同步流程，各平台子类只需实现具体的 API 调用逻辑。
所有数据库交互使用序列化器，保证数据校验和幂等性。
"""

import json
import logging
from abc import ABC

from django.utils.timezone import now

from apps.cloud_platform.sync.schemas import (
    BalanceSyncData,
    DnsRecordSyncData,
    DomainSyncData,
    ServerSyncData,
    SyncResult,
)

logger = logging.getLogger(__name__)


class BaseCloudSyncer(ABC):  # noqa: B024
    """云平台资源同步抽象基类。

    子类需实现 _fetch_* 抽象方法，基类负责调度、安全包装和序列化器 upsert。
    """

    PLATFORM_TYPE: str = ''
    PLATFORM_NAMES: list[str] = []
    SUPPORTED_RESOURCES: set[str] = set()

    def __init__(self, cloud_platform):  # noqa: ANN001
        """初始化同步器。

        Args:
            cloud_platform: CloudPlatform 模型实例。
        """
        self.cloud_platform = cloud_platform

    # ------------------------------------------------------------------
    # 凭据属性
    # ------------------------------------------------------------------

    @property
    def credentials(self) -> dict:
        """获取当前平台的有效凭据信息。

        EncryptedTextField 字段在读取时自动解密，因此可以直接取值。
        返回包含 access_key/access_secret/username/password/api_token/email/extra_data 的字典。
        """
        from apps.cloud_platform.models import Credential

        cred = Credential.objects.filter(platform=self.cloud_platform, is_active=True).first()
        if cred is None:
            return {}
        return {
            'access_key': cred.access_key,
            'access_secret': cred.access_secret,
            'username': cred.username,
            'password': cred.password,
            'api_token': cred.api_token,
            'email': cred.email,
            'extra_data': cred.extra_data or {},
        }

    # ------------------------------------------------------------------
    # 区域解析
    # ------------------------------------------------------------------

    def _parse_regions(self) -> list[str]:
        """解析 cloud_platform.region 为区域列表。

        支持 JSON 数组、逗号/空格/分号分隔的字符串。

        Returns:
            区域标识字符串列表。
        """
        raw = self.cloud_platform.region
        if not raw:
            return []
        raw = raw.strip()
        if raw.startswith('['):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(r) for r in parsed if r]
            except (json.JSONDecodeError, TypeError):
                pass
        # 逗号/分号/空格分隔
        parts = []
        for sep in [',', ';', ' ']:
            if sep in raw:
                parts = [p.strip() for p in raw.split(sep) if p.strip()]
                break
        return parts if parts else [raw]

    # ------------------------------------------------------------------
    # 调度入口
    # ------------------------------------------------------------------

    def sync_all(self, resources: list[str] | None = None) -> dict[str, SyncResult]:
        """执行全部或指定资源类型的同步。

        按资源依赖顺序执行：domain → dns_record（后者依赖前者先写入 Domain 记录）。

        Args:
            resources: 需要同步的资源类型列表，None 表示全部。

        Returns:
            {资源类型: SyncResult} 字典，每个资源类型独立统计。
        """
        # 资源类型执行顺序：domain 必须在 dns_record 之前
        _RESOURCE_ORDER = {'server': 0, 'domain': 1, 'dns_record': 2, 'balance': 3}

        if resources is None:
            resources = list(self.SUPPORTED_RESOURCES)
        else:
            resources = [r for r in resources if r in self.SUPPORTED_RESOURCES]
        resources.sort(key=lambda r: _RESOURCE_ORDER.get(r, 99))

        handlers = {
            'server': self._sync_servers_safe,
            'domain': self._sync_domains_safe,
            'dns_record': self._sync_dns_record_safe,
            'balance': self._sync_balance_safe,
        }

        results: dict[str, SyncResult] = {}
        for resource_type in resources:
            handler = handlers.get(resource_type)
            if handler:
                logger.info('开始同步 [%s] 资源类型: %s', self.PLATFORM_TYPE, resource_type)
                results[resource_type] = handler()

        return results

    # ------------------------------------------------------------------
    # 安全包装方法 — 每个方法返回独立的 SyncResult
    # ------------------------------------------------------------------

    def _sync_servers_safe(self) -> SyncResult:
        """安全包装：同步云服务器。"""
        result = SyncResult(resource_type='server')
        try:
            servers = self._fetch_servers()
        except NotImplementedError:
            logger.info('云服务器同步未实现 [%s]', self.PLATFORM_TYPE)
            return result
        for srv in servers:
            try:
                self._upsert_server(srv, result)
            except Exception:
                logger.exception('同步云服务器失败: %s', srv.hostname)
                result.add_error(srv.hostname, '服务器同步异常')
        return result

    def _sync_domains_safe(self) -> SyncResult:
        """安全包装：同步域名（含企业主体自动匹配与创建）。

        执行顺序：
        1. 获取域名列表（含联系人/企业主体信息）
        2. 逐域名：查找或创建企业主体 → 关联主体到域名 → upsert 域名记录
        """
        result = SyncResult(resource_type='domain')
        try:
            domains = self._fetch_domains()
        except NotImplementedError:
            logger.info('域名同步未实现 [%s]', self.PLATFORM_TYPE)
            return result
        for dm in domains:
            try:
                self._upsert_domain_with_entity(dm, result)
            except Exception:
                logger.exception('同步域名失败: %s', dm.name)
                result.add_error(dm.name, '域名同步异常')
        return result

    def _sync_dns_record_safe(self) -> SyncResult:
        """安全包装：同步 DNS 记录。"""
        result = SyncResult(resource_type='dns_record')
        try:
            records = self._fetch_dns_records()
        except NotImplementedError:
            logger.info('DNS 记录同步未实现 [%s]', self.PLATFORM_TYPE)
            return result
        for rec in records:
            try:
                self._upsert_dns_record(rec, result)
            except Exception:
                logger.exception('同步DNS记录失败: %s.%s', rec.domain_name, rec.host_record)
                result.add_error(f'{rec.domain_name}.{rec.host_record}', 'DNS记录同步异常')
        return result

    def _sync_balance_safe(self) -> SyncResult:
        """安全包装：同步账户余额。"""
        result = SyncResult(resource_type='balance')
        try:
            balance = self._fetch_balance()
        except NotImplementedError:
            logger.info('账户余额同步未实现 [%s]', self.PLATFORM_TYPE)
            return result
        if balance is None:
            return result
        try:
            self._save_balance(balance)
            result.updated += 1
        except Exception:
            logger.exception('保存账户余额失败')
            result.add_error('balance', '账户余额保存异常')
        return result

    # ------------------------------------------------------------------
    # 序列化器驱动的 upsert 方法（幂等性保证）
    # ------------------------------------------------------------------

    def _upsert_server(self, data: ServerSyncData, result: SyncResult) -> None:
        """通过 CloudServerSerializer 新增或更新云服务器（幂等）。

        优先按 instance_id + platform 匹配，其次按 name + platform 匹配。

        Args:
            data: 服务器同步数据。
            result: 同步结果对象，用于累加 created/updated 计数。
        """
        from apps.asset.models import CloudServer
        from apps.asset.serializers import CloudServerSerializer

        status_map = {
            'running': 'running',
            'stopped': 'stopped',
            'starting': 'starting',
            'stopping': 'stopping',
            'rebooting': 'rebooting',
            'pending': 'pending',
            'terminated': 'terminated',
        }
        os_map = {
            'linux': 'linux',
            'windows': 'windows',
            'centos': 'centos',
            'ubuntu': 'ubuntu',
            'debian': 'debian',
            'rhel': 'rhel',
            'coreos': 'coreos',
        }

        serializer_data = {
            'platform': str(self.cloud_platform.pk),
            'name': data.hostname,
            'os_type': os_map.get((data.os or '').lower(), 'other'),
            'status': status_map.get(data.status, 'unknown'),
            'is_active': data.status != 'terminated',
        }
        if data.instance_id:
            serializer_data['instance_id'] = data.instance_id
        if data.cpu_cores is not None:
            serializer_data['cpu'] = data.cpu_cores
        if data.memory_gb is not None:
            serializer_data['memory'] = int(data.memory_gb)
        if data.disk_gb is not None:
            serializer_data['disk_size'] = int(data.disk_gb)
        if data.public_ips:
            serializer_data['public_ip'] = data.public_ips[0]
        if data.private_ips:
            serializer_data['private_ip'] = data.private_ips[0]
        if data.expire_date:
            serializer_data['expire_time'] = data.expire_date
        if data.region:
            serializer_data['region'] = data.region
        if data.tags:
            serializer_data['tags'] = data.tags

        # 幂等查找
        server = None
        if data.instance_id:
            server = CloudServer.objects.filter(instance_id=data.instance_id, platform=self.cloud_platform).first()
        if server is None:
            server = CloudServer.objects.filter(name=data.hostname, platform=self.cloud_platform).first()

        if server:
            s = CloudServerSerializer(server, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
        else:
            s = CloudServerSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            s.save()
            result.created += 1

    def _find_or_create_company(self, entity_info: dict[str, str | None], result: SyncResult):  # noqa: ANN202
        """根据实体信息查找或自动创建 Company 主体。

        匹配优先级：统一社会信用代码 > 公司名称（忽略大小写）。
        若两者均无法匹配，则自动创建新 Company 记录。

        Args:
            entity_info: 实体信息字典，包含 company_name/credit_code/legal_person/
                         company_type/address/contact_person/contact_phone/contact_email。
            result: 同步结果对象，用于累加 companies_created 计数和记录错误。

        Returns:
            Company 实例，查找/创建失败时返回 None。
        """
        from django.db import transaction

        from apps.company.models import Company

        company_name = (entity_info.get('company_name') or '').strip()
        credit_code = (entity_info.get('credit_code') or '').strip()

        if not company_name and not credit_code:
            return None

        company = None
        # 第一步：按统一社会信用代码精确匹配
        if credit_code:
            company = Company.objects.filter(
                unified_social_credit_code=credit_code,
            ).first()
            if company:
                logger.debug('按信用代码匹配到公司主体: %s → %s', credit_code, company.name)

        # 第二步：按公司名称匹配（忽略大小写）
        if company is None and company_name:
            company = Company.objects.filter(name__iexact=company_name).first()
            if company:
                logger.debug('按名称匹配到公司主体: %s', company_name)

        # 第三步：自动创建
        if company is None and company_name:
            try:
                with transaction.atomic():
                    # 个人主体时 company_name 可能是人名，截断到 128
                    name = company_name[:128]
                    company = Company.objects.create(
                        name=name,
                        unified_social_credit_code=credit_code[:18] if credit_code else None,
                        legal_representative=(entity_info.get('legal_person') or '')[:64] or None,
                        registered_address=(entity_info.get('address') or '')[:256] or None,
                        is_active=True,
                    )
                logger.info('自动创建公司主体: %s (信用代码: %s)', company_name, credit_code or '无')
                result.companies_created += 1
            except Exception:
                logger.exception('创建公司主体失败: %s', company_name)
                result.add_error(company_name, '创建公司主体失败')
                return None

        return company

    def _upsert_domain_with_entity(self, data: DomainSyncData, result: SyncResult) -> None:
        """域名同步管线：主体匹配 → 域名 upsert → 关联主体（幂等）。

        执行流程：
        1. 从 DomainSyncData 提取实体信息（企业名称/信用代码/法人/地址等）
        2. 调用 _find_or_create_company 查找或自动创建 Company 主体
        3. 将 Company 外键关联到域名记录，通过 DomainSerializer upsert

        Args:
            data: 域名同步数据（含可选的实体信息字段）。
            result: 同步结果对象，用于累加 created/updated/companies_created 计数。
        """
        from apps.asset.models import Domain
        from apps.asset.serializers import DomainSerializer

        # ---- Step 1: 查找或创建企业主体 ----
        company = None
        entity_info = {
            'company_name': data.company_name,
            'credit_code': data.credit_code,
            'legal_person': data.legal_person,
            'company_type': data.company_type,
            'address': data.address,
            'contact_person': data.contact_person,
            'contact_phone': data.contact_phone,
            'contact_email': data.contact_email,
        }
        # 个人主体（company_type='个人'）：企业名称为空时，用联系人姓名作为公司名称
        if not entity_info['company_name'] and entity_info['contact_person']:
            entity_info['company_name'] = entity_info['contact_person']
            logger.debug(
                '个人主体 [%s] 使用联系人姓名作为公司名称: %s',
                data.name,
                entity_info['contact_person'],
            )

        if any(v for v in entity_info.values() if v):
            company = self._find_or_create_company(entity_info, result)

        # ---- Step 2: 构建序列化器数据并 upsert 域名 ----
        serializer_data: dict = {
            'platform': str(self.cloud_platform.pk),
            'is_active': True,
        }
        if company:
            serializer_data['company'] = str(company.pk)
        # 只设置非空值，避免用空数据覆盖已有信息
        if data.registrar_name:
            serializer_data['registrar'] = data.registrar_name
        if data.register_date:
            serializer_data['registration_time'] = data.register_date
        if data.expire_date:
            serializer_data['expire_time'] = data.expire_date
        if data.dns_provider:
            serializer_data['dns_server'] = data.dns_provider
        if data.owner_name:
            serializer_data['owner_name'] = data.owner_name

        domain = Domain.objects.filter(domain_name=data.name).first()
        if domain:
            s = DomainSerializer(domain, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
            logger.debug('更新域名: %s (company: %s)', data.name, company)
        else:
            serializer_data['domain_name'] = data.name
            s = DomainSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            s.save()
            result.created += 1
            logger.debug('新增域名: %s (company: %s)', data.name, company)

    def _upsert_dns_record(self, data: DnsRecordSyncData, result: SyncResult) -> None:
        """通过 DnsRecordSerializer 新增或更新 DNS 解析记录（幂等）。

        按 domain + record_type + host + value 组合唯一匹配。
        域名不在资产库或 DNS 不由当前平台托管时静默跳过。

        Args:
            data: DNS 记录同步数据。
            result: 同步结果对象，用于累加 created/updated 计数。
        """
        from apps.asset.models import DnsRecord, Domain
        from apps.asset.serializers import DnsRecordSerializer

        domain = Domain.objects.filter(domain_name=data.domain_name).first()
        if not domain:
            # 域名不在资产库中（如 DNSPod 中托管的非腾讯云注册域名），静默跳过
            logger.debug('域名 [%s] 不在资产库中，跳过 DNS 记录', data.domain_name)
            return

        # 检查该域名的 DNS 是否由当前平台管理
        if not self._is_platform_dns(domain):
            logger.debug('域名 [%s] DNS 不由当前平台管理，跳过', data.domain_name)
            return

        record = DnsRecord.objects.filter(
            domain=domain,
            record_type=data.record_type,
            host=data.host_record,
            value=data.record_value,
        ).first()

        serializer_data = {
            'domain': str(domain.pk),
            'record_type': data.record_type,
            'host': data.host_record,
            'value': data.record_value,
            'ttl': data.ttl or 600,
            'priority': data.priority or 0,
            'is_active': True,
        }

        if record:
            s = DnsRecordSerializer(record, data=serializer_data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
            result.updated += 1
        else:
            s = DnsRecordSerializer(data=serializer_data)
            s.is_valid(raise_exception=True)
            s.save()
            result.created += 1

    def _save_balance(self, data: BalanceSyncData) -> None:
        """保存账户余额到 CloudPlatform 和 AccountBalance 快照。

        Args:
            data: 余额同步数据。
        """
        from apps.cloud_platform.models import AccountBalance

        self.cloud_platform.account_balance = data.total_balance
        self.cloud_platform.balance_updated_time = data.recorded_at or now()
        self.cloud_platform.save(update_fields=['account_balance', 'balance_updated_time'])

        today = (data.recorded_at or now()).date()
        AccountBalance.objects.update_or_create(
            platform=self.cloud_platform,
            record_date=today,
            defaults={'balance': data.total_balance},
        )

    # ------------------------------------------------------------------
    # DNS 归属判断 —— 子类可覆盖以匹配平台特定的 DNS 服务器特征
    # ------------------------------------------------------------------

    def _is_platform_dns(self, domain) -> bool:  # noqa: ANN001
        """判断域名 DNS 是否由当前平台管理。

        基类默认返回 True（只要域名存在就视为该平台管理）。
        子类应覆盖此方法，检查 domain.dns_server 是否包含平台 DNS 特征串，
        避免将非本平台托管的 DNS 记录错误同步。

        Args:
            domain: Domain 模型实例。

        Returns:
            True 表示 DNS 由当前平台管理，应同步解析记录。
        """
        return True

    # ------------------------------------------------------------------
    # 数据拉取方法 —— 子类按 SUPPORTED_RESOURCES 选择性实现
    # ------------------------------------------------------------------
    # 安全包装方法（_sync_*_safe）已捕获 NotImplementedError，未实现的资源
    # 类型会被静默跳过，无需在子类中显式实现全部方法。

    def _fetch_servers(self) -> list[ServerSyncData]:
        """获取云服务器列表，子类按需覆盖。

        Returns:
            ServerSyncData 对象列表。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持服务器同步')

    def _fetch_domains(self) -> list[DomainSyncData]:
        """获取域名列表，子类按需覆盖。

        Returns:
            DomainSyncData 对象列表。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持域名同步')

    def _fetch_dns_records(self) -> list[DnsRecordSyncData]:
        """获取 DNS 解析记录列表，子类按需覆盖。

        Returns:
            DnsRecordSyncData 对象列表。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持 DNS 记录同步')

    def _fetch_balance(self) -> BalanceSyncData | None:
        """获取账户余额，子类按需覆盖。

        Returns:
            BalanceSyncData 对象，不支持则返回 None。
        """
        raise NotImplementedError(f'{self.PLATFORM_TYPE} 平台不支持余额同步')
