"""阿里云同步器 — ECS/域名/余额。"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from apps.cloud_platform.sync.base import BaseCloudSyncer
from apps.cloud_platform.sync.engine import register_syncer
from apps.cloud_platform.sync.schemas import (
    BalanceSyncData,
    DomainSyncData,
    ServerSyncData,
)

logger = logging.getLogger(__name__)

try:
    from alibabacloud_bssopenapi20171214.client import Client as BssClient
    from alibabacloud_domain20180129.client import Client as DomainClient
    from alibabacloud_domain20180129.models import QueryDomainListRequest
    from alibabacloud_ecs20140526.client import Client as EcsClient
    from alibabacloud_ecs20140526.models import DescribeInstancesRequest
    from alibabacloud_tea_openapi.models import Config as AliConfig

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning(
        '阿里云 SDK 未安装: pip install alibabacloud-ecs20140526 '
        'alibabacloud-domain20180129 alibabacloud-bssopenapi20171214'
    )

PAGE_SIZE = 50


@register_syncer
class AliyunCloudSyncer(BaseCloudSyncer):
    """阿里云资源同步器。

    支持资源类型：
    - server: ECS 云服务器
    - domain: 域名注册
    - balance: 账户余额
    """

    PLATFORM_TYPE = 'aliyun'
    PLATFORM_NAMES = ['阿里云', 'aliyun', 'alibaba', 'alibabacloud']
    SUPPORTED_RESOURCES = {'server', 'domain', 'balance'}

    def __init__(self, cloud_platform):  # noqa: ANN001
        """初始化阿里云同步器。

        Args:
            cloud_platform: CloudPlatform 模型实例。
        """
        super().__init__(cloud_platform)
        self._ak = ''
        self._sk = ''
        self._regions: list[str] = []

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _setup(self) -> bool:
        """初始化 AK/SK 和区域配置。

        Returns:
            True 表示配置有效，可以发起 API 调用。
        """
        if not SDK_AVAILABLE:
            return False
        creds = self.credentials
        self._ak = creds.get('access_key', '')
        self._sk = creds.get('access_secret', '')
        self._regions = self._parse_regions()
        if not self._regions:
            self._regions = ['cn-hangzhou']
        return bool(self._ak)

    def _build_config(self, region=None):  # noqa: ANN001, ANN202
        """构建阿里云 OpenAPI 配置。

        Args:
            region: 区域标识（如 cn-hangzhou）。

        Returns:
            AliConfig 配置对象。
        """
        cfg = AliConfig(access_key_id=self._ak, access_key_secret=self._sk)
        if region:
            cfg.region_id = region
        return cfg

    # ------------------------------------------------------------------
    # 云服务器 (ECS)
    # ------------------------------------------------------------------

    def _fetch_servers(self) -> list[ServerSyncData]:
        """获取所有区域的 ECS 实例列表（幂等：同参数多次调用返回相同数据）。"""
        if not self._setup():
            return []
        results: list[ServerSyncData] = []
        status_map = {
            'Running': 'running',
            'Stopped': 'stopped',
            'Starting': 'starting',
            'Stopping': 'stopping',
            'Pending': 'pending',
        }
        for region in self._regions:
            try:
                client = EcsClient(self._build_config(region))
                client.endpoint = f'ecs.{region}.aliyuncs.com'
                page = 1
                while True:
                    req = DescribeInstancesRequest(region_id=region, page_size=PAGE_SIZE, page_number=page)
                    resp = client.describe_instances(req)
                    body = resp.body
                    instances = body.instances.instance if body.instances else []
                    if not instances:
                        break
                    for inst in instances:
                        # 公网 IP
                        public_ips: list[str] = []
                        if inst.eip_address and inst.eip_address.ip_address:
                            public_ips.append(inst.eip_address.ip_address)
                        if inst.public_ip_address and inst.public_ip_address.ip_address:
                            public_ips.extend(ip for ip in inst.public_ip_address.ip_address if ip)
                        # 内网 IP
                        private_ips: list[str] = []
                        if inst.network_interfaces and inst.network_interfaces.network_interface:
                            for ni in inst.network_interfaces.network_interface:
                                if ni.primary_ip_address:
                                    private_ips.append(ni.primary_ip_address)
                        # 到期时间
                        expire = None
                        if inst.expired_time:
                            try:
                                expire = date.fromisoformat(inst.expired_time[:10])
                            except (ValueError, TypeError):
                                pass
                        # 系统盘大小
                        disk = None
                        if inst.system_disk and inst.system_disk.size:
                            try:
                                disk = float(inst.system_disk.size)
                            except (ValueError, TypeError):
                                pass
                        # 标签
                        tags: dict[str, str] = {}
                        if inst.tags and inst.tags.tag:
                            for t in inst.tags.tag:
                                if t.tag_key:
                                    tags[t.tag_key] = t.tag_value or ''
                        # 状态
                        status = inst.status or ''
                        status = status_map.get(status, status.lower())
                        results.append(
                            ServerSyncData(
                                hostname=inst.instance_name or inst.host_name or '',
                                instance_id=inst.instance_id or '',
                                status=status,
                                os=inst.os_name or inst.os_type or '',
                                cpu_cores=int(inst.cpu) if inst.cpu else None,
                                memory_gb=float(inst.memory) / 1024.0 if inst.memory else None,
                                disk_gb=disk,
                                public_ips=public_ips,
                                private_ips=private_ips,
                                expire_date=expire,
                                region=region,
                                tags=tags,
                            )
                        )
                    if page * PAGE_SIZE >= (body.total_count or 0):
                        break
                    page += 1
            except Exception:
                logger.exception('阿里云区域[%s] ECS 实例拉取失败', region)
        return results

    # ------------------------------------------------------------------
    # 域名
    # ------------------------------------------------------------------

    def _fetch_domains(self) -> list[DomainSyncData]:
        """获取所有域名列表（幂等：同参数多次调用返回相同数据）。"""
        if not self._setup():
            return []
        results: list[DomainSyncData] = []
        try:
            client = DomainClient(self._build_config())
            client.endpoint = 'domain.aliyuncs.com'
            page = 1
            while True:
                req = QueryDomainListRequest(page_num=page, page_size=PAGE_SIZE)
                resp = client.query_domain_list(req)
                body = resp.body
                dms = body.data.domain if body.data else []
                if not dms:
                    break
                for dm in dms:
                    rd = None
                    ed = None
                    if dm.registration_date:
                        try:
                            rd = date.fromisoformat(dm.registration_date[:10])
                        except (ValueError, TypeError):
                            pass
                    if dm.expiration_date:
                        try:
                            ed = date.fromisoformat(dm.expiration_date[:10])
                        except (ValueError, TypeError):
                            pass
                    st = ''
                    if dm.domain_status:
                        st = (
                            dm.domain_status.split(',')[0].strip()
                            if isinstance(dm.domain_status, str)
                            else str(dm.domain_status)
                        )
                    results.append(
                        DomainSyncData(
                            name=dm.domain_name or '',
                            registrar_name=dm.registrar_name or '',
                            register_date=rd,
                            expire_date=ed,
                            dns_provider=dm.dns_servers or '',
                            status=st,
                            owner_name=dm.registrant_name or dm.registrant_organization or '',
                        )
                    )
                if page * PAGE_SIZE >= (body.total_item_num or 0):
                    break
                page += 1
        except Exception:
            logger.exception('阿里云域名列表拉取失败')
        return results

    # ------------------------------------------------------------------
    # 账户余额
    # ------------------------------------------------------------------

    def _is_platform_dns(self, domain) -> bool:  # noqa: ANN001
        """判断域名 DNS 是否由阿里云管理。

        阿里云 DNS：ns1.alidns.com 等。

        Args:
            domain: Domain 模型实例。

        Returns:
            True 表示 DNS 托管在阿里云。
        """
        dns = (domain.dns_server or '').lower()
        return 'alidns' in dns

    def _fetch_balance(self) -> BalanceSyncData | None:
        """获取账户余额（幂等：同参数多次调用返回相同数据）。

        Returns:
            余额数据，失败时返回 None。
        """
        if not self._setup():
            return None
        try:
            client = BssClient(self._build_config('cn-hangzhou'))
            client.endpoint = 'business.aliyuncs.com'
            resp = client.query_account_balance()
            if resp.body.data is None:
                return None
            amount_str = resp.body.data.available_amount or '0'
            cleaned = amount_str.strip().replace(',', '')
            if cleaned and cleaned[0] in ('¥', '$', '￥', '€', '£'):
                cleaned = cleaned[1:]
            balance = Decimal(cleaned) if cleaned else Decimal('0')
            return BalanceSyncData(
                total_balance=balance,
                currency='CNY',
                recorded_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception('阿里云账户余额拉取失败')
            return None
