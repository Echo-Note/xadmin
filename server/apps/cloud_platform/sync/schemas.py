"""同步数据协议 — Pydantic 模型定义云平台资源同步的数据传输对象。

所有同步器通过 Pydantic 模型传递数据，提供类型校验和序列化能力。
数据库写入由 DRF Serializer 负责（见 base.py）。
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ServerSyncData(BaseModel):
    """云服务器同步数据 — 各云平台拉取的 CVM/ECS/VM 统一格式。"""

    hostname: str = Field(default='', description='实例名称')
    instance_id: str = Field(default='', description='云平台实例 ID')
    status: str = Field(
        default='running', description='运行状态：running/stopped/starting/stopping/rebooting/pending/terminated'
    )
    os: str = Field(default='', description='操作系统名称')
    cpu_cores: int | None = Field(default=None, description='CPU 核心数')
    memory_gb: float | None = Field(default=None, description='内存大小(GB)')
    disk_gb: float | None = Field(default=None, description='系统盘大小(GB)')
    public_ips: list[str] = Field(default_factory=list, description='公网 IP 列表')
    private_ips: list[str] = Field(default_factory=list, description='内网 IP 列表')
    expire_date: date | None = Field(default=None, description='到期日期')
    region: str = Field(default='', description='所属区域标识')
    tags: dict[str, str] = Field(default_factory=dict, description='云厂商标签键值对')


class DomainSyncData(BaseModel):
    """域名同步数据 — 各注册商拉取的域名统一格式。"""

    name: str = Field(default='', description='域名，如 example.com')
    registrar_name: str = Field(default='', description='注册商名称')
    register_date: date | None = Field(default=None, description='注册日期')
    expire_date: date | None = Field(default=None, description='到期日期')
    dns_provider: str = Field(default='', description='DNS 服务商')
    status: str = Field(default='', description='域名状态')
    owner_name: str = Field(default='', description='所有者姓名')
    # 归属主体信息（部分云平台 API 返回）
    company_name: str | None = Field(default=None, description='企业名称')
    credit_code: str | None = Field(default=None, description='统一社会信用代码')
    legal_person: str | None = Field(default=None, description='法定代表人')
    company_type: str | None = Field(default=None, description='主体类型')
    address: str | None = Field(default=None, description='注册地址')
    contact_person: str | None = Field(default=None, description='联系人')
    contact_phone: str | None = Field(default=None, description='联系电话')
    contact_email: str | None = Field(default=None, description='联系邮箱')


class DnsRecordSyncData(BaseModel):
    """DNS 解析记录同步数据。"""

    domain_name: str = Field(default='', description='所属域名')
    record_type: str = Field(default='A', description='记录类型：A/AAAA/CNAME/MX/TXT/NS/SRV/CAA')
    host_record: str = Field(default='@', description='主机记录，@ 表示根域名')
    record_value: str = Field(default='', description='解析目标值')
    ttl: int = Field(default=600, ge=1, description='生存时间(秒)')
    priority: int = Field(default=0, ge=0, description='MX/SRV 记录优先级')
    line: str = Field(default='默认', description='解析线路')


class BalanceSyncData(BaseModel):
    """账户余额同步数据。"""

    total_balance: Decimal = Field(default=Decimal('0'), description='账户总余额')
    cash_balance: Decimal | None = Field(default=None, description='现金余额')
    voucher_balance: Decimal | None = Field(default=None, description='代金券余额')
    credit_balance: Decimal | None = Field(default=None, description='信用额度')
    frozen_amount: Decimal | None = Field(default=None, description='冻结金额')
    currency: str = Field(default='CNY', description='货币单位')
    recorded_at: datetime | None = Field(default=None, description='余额记录时间')


class SyncResult(BaseModel):
    """单次资源类型的同步结果汇总 — 幂等，重复累加不产生副作用。"""

    resource_type: str = Field(default='', description='资源类型：server/domain/dns_record/balance')
    created: int = Field(default=0, ge=0, description='新建数量')
    updated: int = Field(default=0, ge=0, description='更新数量')
    terminated: int = Field(default=0, ge=0, description='终止数量')
    companies_created: int = Field(default=0, ge=0, description='自动创建的企业主体数量')
    errors: list[dict] = Field(default_factory=list, description='错误列表，每项: {item, error}')

    def add_error(self, item: str, error: str) -> None:
        """记录一条同步错误。"""
        self.errors.append({'item': item, 'error': error})

    def merge(self, other: 'SyncResult') -> None:
        """合并另一个 SyncResult 的计数和错误。"""
        self.created += other.created
        self.updated += other.updated
        self.terminated += other.terminated
        self.companies_created += other.companies_created
        self.errors.extend(other.errors)

    @property
    def total_changes(self) -> int:
        """所有变更总数。"""
        return self.created + self.updated + self.terminated

    @property
    def has_errors(self) -> bool:
        """是否有错误。"""
        return len(self.errors) > 0
