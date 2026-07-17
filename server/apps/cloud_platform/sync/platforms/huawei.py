"""华为云同步器 — ECS/域名/余额。"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from apps.cloud_platform.sync.base import BaseCloudSyncer
from apps.cloud_platform.sync.registry import register_syncer
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
    """华为云平台同步器 — 仅负责 API 数据拉取和格式转换。"""

    PLATFORM_TYPE = 'huawei'
    PLATFORM_NAMES = ['华为云', 'huawei', 'huaweicloud']
    SUPPORTED_RESOURCES = {'server', 'domain', 'balance'}

    def __init__(self, cloud_platform) -> None:  # noqa: ANN001, D107
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
        return self.regions[0] if self.regions else 'cn-north-4'

    def _build_credentials(self):  # noqa: ANN202
        return BasicCredentials(self._ak, self._sk)

    # ---------- ECS 服务器同步 ----------

    @staticmethod
    def _parse_hw_date(dt_str: str | None) -> date | None:
        """解析华为云日期时间字符串。

        Args:
            dt_str: 形如 '2024-01-15T10:30:00Z' 的 ISO 时间字符串。

        Returns:
            date 对象或 None。
        """
        if not dt_str:
            return None
        try:
            return date.fromisoformat(dt_str[:10])
        except (ValueError, TypeError):
            return None

    def _build_ecs_client(self, region: str):  # noqa: ANN202
        """构建指定区域的 ECS 客户端。

        Args:
            region: 区域标识，如 cn-north-4。

        Returns:
            配置好的 EcsClient 实例。
        """
        return (
            EcsClient()
            .with_credentials(self._build_credentials())
            .with_region(region)
            .with_http_config(HttpConfig.get_default_config())
        )

    def _fetch_servers_for_region(self, region: str) -> list[ServerSyncData]:
        """拉取单个区域的 ECS 实例列表。

        Args:
            region: 区域标识，如 cn-north-4。

        Returns:
            该区域的 ServerSyncData 列表。
        """
        results: list[ServerSyncData] = []
        status_map = {
            'ACTIVE': 'running',
            'SHUTOFF': 'stopped',
            'REBOOT': 'rebooting',
            'HARD_REBOOT': 'rebooting',
            'ERROR': 'stopped',
            'BUILD': 'pending',
            'REBUILD': 'pending',
            'RESIZE': 'pending',
            'VERIFY_RESIZE': 'pending',
        }

        client = self._build_ecs_client(region)
        marker = None
        while True:
            req = ListServersDetailsRequest(limit=100, marker=marker)
            resp = self._retry(
                lambda req=req: client.list_servers_details(req),
                label=f'ECS-{region}',
            )
            if resp is None:
                break
            if not resp.servers:
                break

            for srv in resp.servers:
                # ——— IP 分类：按 OS-EXT-IPS:type 区分公网/内网 ———
                public_ips: list[str] = []
                private_ips: list[str] = []
                ip_map = srv.addresses or {}
                for _vpc_name, vpc_ips in ip_map.items():
                    for addr in vpc_ips:
                        ip = getattr(addr, 'addr', '') or ''
                        if not ip:
                            continue
                        ip_type = getattr(addr, 'OS-EXT-IPS:type', '') or ''
                        # 华为云固定 IP（floating）为公网，其他为内网
                        if ip_type.lower() == 'floating':
                            if ip not in public_ips:
                                public_ips.append(ip)
                        else:
                            if ip not in private_ips:
                                private_ips.append(ip)

                # ——— 规格信息 ———
                cpu_cores = None
                memory_gb = None
                disk_gb = None
                if srv.flavor:
                    if srv.flavor.vcpus:
                        try:
                            cpu_cores = int(srv.flavor.vcpus)
                        except (ValueError, TypeError):
                            pass
                    if srv.flavor.ram:
                        try:
                            memory_gb = float(int(srv.flavor.ram) / 1024)
                        except (ValueError, TypeError):
                            pass
                    # flavor.disk 是规格总磁盘，不是系统盘，不直接使用
                    # 从 image 或 volume_attached 获取更准确的磁盘信息
                    disk_gb = self._extract_disk_from_server(srv)

                # ——— 操作系统 ———
                os_name, os_version = self._extract_os_info(srv)

                # ——— 创建时间 ———
                creation = self._parse_hw_date(srv.created)

                # ——— 标签（从 metadata 提取自定义标签） ———
                tags: dict[str, str] = {}
                if srv.metadata:
                    for k, v in srv.metadata.items():
                        if isinstance(v, str):
                            tags[k] = v

                results.append(
                    ServerSyncData(
                        hostname=srv.name or '',
                        instance_id=srv.id or '',
                        status=status_map.get(srv.status or '', (srv.status or '').lower()),
                        os=os_name,
                        os_version=os_version,
                        cpu_cores=cpu_cores,
                        memory_gb=memory_gb,
                        disk_gb=disk_gb,
                        public_ips=public_ips,
                        private_ips=private_ips,
                        region=region,
                        tags=tags,
                        instance_charge_type='',  # 需额外调用 BSS 接口获取
                        creation_date=creation,
                        instance_type=srv.flavor.id if srv.flavor else '',
                    )
                )

            marker = resp.servers[-1].id if resp.servers else None
            if not marker:
                break

        return results

    @staticmethod
    def _extract_disk_from_server(srv) -> float | None:  # noqa: ANN001
        """从服务器详细信息中提取系统盘大小。

        优先从 os-extended-volumes:volumes_attached 提取，
        其次从 image 元数据估算。

        Args:
            srv: 华为云 Server 对象。

        Returns:
            系统盘大小(GB)或 None。
        """
        # 从挂载的卷中找系统盘（通常第一个 boot 卷）
        try:
            attached = getattr(srv, 'os-extended-volumes:volumes_attached', None) or []
            for vol in attached:
                if isinstance(vol, dict) and vol.get('bootable') == 'true':
                    size = vol.get('size')
                    if size:
                        return float(size)
                # 如果只有一个卷，假定为系统盘
                if len(attached) == 1 and isinstance(vol, dict):
                    size = vol.get('size')
                    if size:
                        return float(size)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_os_info(srv) -> tuple[str, str]:  # noqa: ANN001
        """从服务器元数据中提取操作系统名称和版本。

        Args:
            srv: 华为云 Server 对象。

        Returns:
            (os_name, os_version) 元组。
        """
        os_name = ''
        os_version = ''
        if srv.metadata:
            # 优先取 os_type
            os_name = srv.metadata.get('os_type', '') or ''
            # 尝试取镜像名称作为版本
            os_version = srv.metadata.get('image_name', '') or srv.metadata.get('os_version', '') or ''
        # 回退：从 image 对象取
        if not os_name and hasattr(srv, 'image') and srv.image:
            img = srv.image
            if isinstance(img, dict):
                os_name = img.get('name', '') or img.get('os_type', '')
            else:
                os_name = getattr(img, 'name', '') or getattr(img, 'os_type', '') or ''
        return os_name, os_version

    def _fetch_servers(self) -> list[ServerSyncData]:
        """获取所有区域的 ECS 实例列表（幂等）。

        支持并行拉取多区域，通过基类 _fetch_by_regions 实现。
        """
        if not self._setup():
            return []
        return self._fetch_by_regions(self._fetch_servers_for_region)

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
            from huaweicloudsdkcore.auth.credentials import BasicCredentials
            from huaweicloudsdkcore.sdk_request import SdkRequest
            from huaweicloudsdkcore.signer.signer import Signer

            creds = BasicCredentials(self._ak, self._sk)
            signer = Signer(creds)

            # BSS 余额查询 API — 使用全局端点 GET 请求
            host = 'bss.myhuaweicloud.com'
            path = '/v2/accounts/customer-accounts/balances'
            date_str = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')

            sdk_req = SdkRequest(
                method='GET',
                host=host,
                resource_path=path,
                header_params={'Content-Type': 'application/json', 'X-Sdk-Date': date_str},
                query_params=[],
                body='',
            )
            signed = signer.sign(sdk_req)

            req = requests.Request(
                'GET',
                f'https://{host}{path}',
                headers=dict(signed.header_params),
            )
            resp = requests.Session().send(req.prepare(), timeout=30)
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
