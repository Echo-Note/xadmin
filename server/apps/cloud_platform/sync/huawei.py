"""华为云同步器 — ECS/域名/余额。"""

import logging
from datetime import UTC, datetime
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
    from huaweicloudsdkcore.auth.credentials import BasicCredentials
    from huaweicloudsdkcore.http.http_config import HttpConfig
    from huaweicloudsdkdns.v2 import DnsClient, ListPublicZonesRequest
    from huaweicloudsdkecs.v2 import EcsClient, ListServersDetailsRequest

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning('华为云 SDK 未安装: pip install huaweicloudsdkecs huaweicloudsdkdns')


@register_syncer
class HuaweiCloudSyncer(BaseCloudSyncer):
    """华为云平台同步器。"""

    PLATFORM_TYPE = 'huawei'
    PLATFORM_NAMES = ['华为云', 'huawei', 'huaweicloud']
    SUPPORTED_RESOURCES = {'server', 'domain', 'balance'}

    def __init__(self, cloud_platform):  # noqa: ANN001, D107
        super().__init__(cloud_platform)
        self._ak = ''
        self._sk = ''

    def _setup(self) -> bool:
        if not SDK_AVAILABLE:
            return False
        creds = self.credentials
        self._ak = creds.get('access_key', '')
        self._sk = creds.get('access_secret', '')
        return bool(self._ak)

    def _get_region(self) -> str:
        regions = self._parse_regions()
        return regions[0] if regions else 'cn-north-4'

    def _build_credentials(self):  # noqa: ANN202
        return BasicCredentials(self._ak, self._sk)

    # ---------- ECS 服务器同步 ----------

    def _fetch_servers(self) -> list[ServerSyncData]:
        if not self._setup():
            return []
        results = []
        region = self._get_region()
        try:
            client = (
                EcsClient()
                .with_credentials(self._build_credentials())
                .with_region(region)
                .with_http_config(HttpConfig.get_default_config())
            )
            marker = None
            while True:
                req = ListServersDetailsRequest(limit=100, marker=marker)
                resp = client.list_servers_details(req)
                if not resp.servers:
                    break
                for srv in resp.servers:
                    sm = {
                        'ACTIVE': 'running',
                        'SHUTOFF': 'stopped',
                        'REBOOT': 'rebooting',
                        'HARD_REBOOT': 'rebooting',
                    }
                    ip_map = srv.addresses or {}
                    all_ips = []
                    for vpc_ips in ip_map.values():
                        for addr in vpc_ips:
                            if hasattr(addr, 'addr') and addr.addr:
                                all_ips.append(addr.addr)
                    cpu_cores = None
                    memory_gb = None
                    disk_gb = None
                    if srv.flavor:
                        if srv.flavor.vcpus:
                            try:
                                cpu_cores = int(srv.flavor.vcpus)  # noqa: E701
                            except:  # noqa: E722
                                pass
                        if srv.flavor.ram:
                            try:
                                memory_gb = float(int(srv.flavor.ram) / 1024)  # noqa: E701
                            except:  # noqa: E722
                                pass
                        if srv.flavor.disk:
                            try:
                                disk_gb = float(int(srv.flavor.disk))  # noqa: E701
                            except:  # noqa: E722
                                pass
                    os_name = ''
                    if srv.metadata and 'os_type' in srv.metadata:
                        os_name = srv.metadata['os_type']
                    results.append(
                        ServerSyncData(
                            hostname=srv.name or '',
                            instance_id=srv.id or '',
                            status=sm.get(srv.status or '', 'unknown'),
                            os=os_name,
                            cpu_cores=cpu_cores,
                            memory_gb=memory_gb,
                            disk_gb=disk_gb,
                            public_ips=all_ips,
                            private_ips=all_ips,
                            region=region,
                        )
                    )
                marker = resp.servers[-1].id if resp.servers else None
                if not marker:
                    break
        except Exception:
            logger.exception('华为云ECS拉取失败')
        return results

    # ---------- 域名同步（DNS公共域名） ----------

    def _fetch_domains(self) -> list[DomainSyncData]:
        if not self._setup():
            return []
        results = []
        try:
            client = (
                DnsClient()
                .with_credentials(self._build_credentials())
                .with_region(self._get_region())
                .with_http_config(HttpConfig.get_default_config())
            )
            marker = None
            while True:
                req = ListPublicZonesRequest(limit=100, marker=marker)
                resp = client.list_public_zones(req)
                if not resp.zones:
                    break
                for zone in resp.zones:
                    results.append(
                        DomainSyncData(
                            name=(zone.name or '').rstrip('.'),
                            dns_provider='华为云DNS',
                            status=zone.status or '',
                        )
                    )
                marker = resp.metadata.marker if resp.metadata else None
                if not marker:
                    break
        except Exception:
            logger.exception('华为云域名拉取失败')
        return results

    # ---------- 余额同步（BSS REST API） ----------

    def _fetch_balance(self) -> BalanceSyncData | None:
        import requests

        if not self._setup():
            return None
        try:
            from huaweicloudsdkcore.signer import Signer

            region = self._get_region()
            endpoint = f'https://bss.{region}.myhuaweicloud.com'
            url = f'{endpoint}/v2/accounts/customer-accounts/balances'
            signer = Signer()
            signer.Key = self._ak
            signer.Secret = self._sk
            http_req = signer.Sign(requests.Request('POST', url))
            resp = requests.Session().send(http_req.prepare(), timeout=30)
            data = resp.json()
            total = Decimal('0')
            for acct in data.get('account_balances', []):
                total += Decimal(str(acct.get('amount', 0)))
            return BalanceSyncData(
                total_balance=total,
                currency='CNY',
                recorded_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception('华为云余额拉取失败')
            return None
