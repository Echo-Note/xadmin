"""资产管理应用的模型定义。

包含四大资产类型：
- CloudServer: 云服务器资产
- Domain: 域名资产
- LocalServer: 本地物理服务器
- LocalVM: 本地虚拟主机

所有模型继承 DbAuditModel + DbUuidModel，支持导入导出和审计追溯。
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.module_loading import import_string
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from apps.asset.choices import (
    DnsRecordTypeChoices,
    DomainStatusChoices,
    HypervisorTypeChoices,
    ServerOSTypeChoices,
    ServerStatusChoices,
)
from apps.cloud_platform.models import CloudPlatform
from apps.common.core.models import DbAuditModel, DbUuidModel, upload_directory_path
from apps.company.models import Company


@deconstructible
class PydanticListValidator:
    """使用 Pydantic 模型逐项校验 JSON 列表的可序列化校验器。

    通过 @deconstructible 确保 Django 迁移系统能正确序列化此校验器。
    """

    def __init__(self, model_path: str) -> None:
        """初始化校验器。

        Args:
            model_path: Pydantic 模型的完整路径字符串，如 'apps.asset.structs.CpuDetailItem'。
        """
        self.model_path = model_path
        self._model: type[BaseModel] | None = None

    @property
    def model(self) -> type[BaseModel]:
        """延迟加载 Pydantic 模型。"""
        if self._model is None:
            self._model = import_string(self.model_path)
        return self._model

    def __call__(self, value: Any) -> None:
        """校验 JSON 数据。

        Args:
            value: JSON 列表数据。

        Raises:
            ValidationError: 校验失败。
        """
        if not isinstance(value, list):
            return
        errors = []
        for idx, item in enumerate(value):
            try:
                self.model(**item)
            except PydanticValidationError as e:
                for err in e.errors():
                    loc = '.'.join(str(p) for p in err['loc'])
                    errors.append(f'第 {idx + 1} 项.{loc}: {err["msg"]}')
        if errors:
            raise ValidationError(errors)

    def __eq__(self, other: object) -> bool:
        """比较两个校验器是否等价。

        Args:
            other: 另一个校验器实例。

        Returns:
            是否等价。
        """
        if isinstance(other, PydanticListValidator):
            return self.model_path == other.model_path
        return False


# =============================================================================
# 云服务器
# =============================================================================


class CloudServer(DbAuditModel, DbUuidModel):
    """云服务器资产，记录各云平台上运行的虚拟机实例信息。

    关联平台通过 platform 外键指向 CloudPlatform，可通过平台凭据
    API 实现资产同步。
    """

    name = models.CharField(
        max_length=128,
        verbose_name='实例名称',
        help_text='云服务器实例名称，如 Web-Server-01',
        db_comment='云服务器实例名称',
    )
    platform = models.ForeignKey(
        to=CloudPlatform,
        on_delete=models.PROTECT,
        related_name='cloud_servers',
        verbose_name='归属云平台',
        help_text='该云服务器归属的云平台实例',
        db_comment='归属云平台实例ID，关联cloudplatform表',
    )
    instance_id = models.CharField(
        max_length=128,
        verbose_name='实例 ID',
        help_text='云厂商分配的实例唯一标识，如 ins-xxxxx',
        db_comment='云厂商实例ID',
    )
    public_ip = models.GenericIPAddressField(
        verbose_name='公网 IP',
        null=True,
        blank=True,
        help_text='公网 IPv4 地址',
        db_comment='公网IP地址',
    )
    private_ip = models.GenericIPAddressField(
        verbose_name='内网 IP',
        null=True,
        blank=True,
        help_text='内网 / VPC 私有 IPv4 地址',
        db_comment='内网IP地址',
    )
    os_type = models.CharField(
        max_length=32,
        choices=ServerOSTypeChoices,
        default=ServerOSTypeChoices.LINUX,
        verbose_name='操作系统类型',
        help_text='服务器操作系统类型枚举',
        db_comment='操作系统类型枚举值',
    )
    os_version = models.CharField(
        max_length=64,
        verbose_name='操作系统版本',
        null=True,
        blank=True,
        help_text='操作系统详细版本号，如 Ubuntu 22.04 LTS',
        db_comment='操作系统版本号',
    )
    cpu = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='CPU 核数',
        help_text='vCPU 核心数量',
        db_comment='CPU核数',
    )
    memory = models.PositiveIntegerField(
        default=0,
        verbose_name='内存（GB）',
        help_text='内存大小，单位 GB',
        db_comment='内存大小（GB）',
    )
    disk_size = models.PositiveIntegerField(
        default=0,
        verbose_name='系统盘（GB）',
        help_text='系统盘容量，单位 GB',
        db_comment='系统盘容量（GB）',
    )
    region = models.CharField(
        max_length=128,
        verbose_name='区域',
        null=True,
        blank=True,
        help_text='云厂商区域标识，如 ap-guangzhou',
        db_comment='云厂商区域标识',
    )
    status = models.CharField(
        max_length=32,
        choices=ServerStatusChoices,
        default=ServerStatusChoices.RUNNING,
        verbose_name='运行状态',
        help_text='服务器当前运行状态',
        db_comment='服务器运行状态枚举值',
    )
    expire_time = models.DateTimeField(
        verbose_name='到期时间',
        null=True,
        blank=True,
        help_text='实例到期时间，包年包月实例需关注',
        db_comment='实例到期时间',
    )
    tags = models.JSONField(
        verbose_name='标签',
        null=True,
        blank=True,
        default=dict,
        help_text='云厂商标签键值对（JSON），用于分类筛选',
        db_comment='云厂商标签JSON',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='启用状态',
        help_text='是否纳入资产管理范围',
        db_comment='启用状态：True启用/False禁用',
    )
    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cloud_servers',
        verbose_name='所属公司',
        help_text='资产归属的公司主体',
        db_comment='归属公司主体ID，关联company表',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = '云服务器'
        verbose_name_plural = verbose_name
        ordering = ['platform', '-created_time']
        db_table_comment = '云服务器资产表，记录各云平台的虚拟机实例信息'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f'{self.platform.name} - {self.name} ({self.instance_id})'


# =============================================================================
# 域名
# =============================================================================


class Domain(DbAuditModel, DbUuidModel):
    """域名资产，记录注册的域名信息及 SSL 证书状态。"""

    domain_name = models.CharField(
        max_length=256,
        unique=True,
        verbose_name='域名',
        help_text='完整域名，如 example.com，唯一',
        db_comment='完整域名，唯一',
    )
    registrar = models.CharField(
        max_length=128,
        verbose_name='注册商',
        null=True,
        blank=True,
        help_text='域名注册服务商，如 腾讯云/阿里云/GoDaddy',
        db_comment='域名注册商名称',
    )
    platform = models.ForeignKey(
        to=CloudPlatform,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='domains',
        verbose_name='归属云平台',
        help_text='域名解析所在的云平台（可选）',
        db_comment='归属云平台实例ID，关联cloudplatform表',
    )
    registration_time = models.DateField(
        verbose_name='注册时间',
        null=True,
        blank=True,
        help_text='域名首次注册日期',
        db_comment='域名注册日期',
    )
    expire_time = models.DateField(
        verbose_name='到期时间',
        null=True,
        blank=True,
        help_text='域名到期日期',
        db_comment='域名到期日期',
    )
    dns_server = models.TextField(
        verbose_name='DNS 服务器',
        null=True,
        blank=True,
        help_text='DNS 服务器列表，多个用逗号或换行分隔',
        db_comment='DNS解析服务器列表',
    )
    status = models.CharField(
        max_length=32,
        choices=DomainStatusChoices,
        default=DomainStatusChoices.ACTIVE,
        verbose_name='域名状态',
        help_text='域名当前状态',
        db_comment='域名状态枚举值',
    )
    owner_name = models.CharField(
        max_length=128,
        verbose_name='所有者',
        null=True,
        blank=True,
        help_text='域名所有者/联系人姓名',
        db_comment='域名所有者姓名',
    )
    is_ssl_enabled = models.BooleanField(
        default=False,
        verbose_name='SSL 证书',
        help_text='是否已部署 SSL 证书',
        db_comment='是否启用SSL证书',
    )
    ssl_expire_time = models.DateField(
        verbose_name='SSL 到期时间',
        null=True,
        blank=True,
        help_text='SSL 证书到期日期',
        db_comment='SSL证书到期日期',
    )

    # --- 证书与责任人 ---
    domain_certificate = models.FileField(
        verbose_name='域名证书',
        upload_to=upload_directory_path,
        null=True,
        blank=True,
        help_text='域名注册证书/实名认证证书扫描件',
        db_comment='域名证书文件路径',
    )
    security_contact = models.CharField(
        max_length=64,
        verbose_name='安全责任人',
        null=True,
        blank=True,
        help_text='域名安全责任人姓名',
        db_comment='安全责任人姓名',
    )
    security_contact_phone = models.CharField(
        max_length=32,
        verbose_name='安全责任人电话',
        null=True,
        blank=True,
        help_text='安全责任人联系电话',
        db_comment='安全责任人电话',
    )
    service_contact = models.CharField(
        max_length=64,
        verbose_name='服务负责人',
        null=True,
        blank=True,
        help_text='域名服务/运维负责人姓名',
        db_comment='服务负责人姓名',
    )
    service_contact_phone = models.CharField(
        max_length=32,
        verbose_name='服务负责人电话',
        null=True,
        blank=True,
        help_text='服务负责人联系电话',
        db_comment='服务负责人电话',
    )

    # --- 备案信息 ---
    icp_number = models.CharField(
        max_length=64,
        verbose_name='ICP 备案号',
        null=True,
        blank=True,
        help_text='ICP 备案号，如 京ICP备2023000001号',
        db_comment='ICP备案号',
    )
    icp_filing_date = models.DateField(
        verbose_name='ICP 备案日期',
        null=True,
        blank=True,
        help_text='ICP 备案通过日期',
        db_comment='ICP备案日期',
    )
    ps_filing_number = models.CharField(
        max_length=64,
        verbose_name='公安备案号',
        null=True,
        blank=True,
        help_text='公安联网备案号，如 京公网安备110100000001号',
        db_comment='公安备案号',
    )
    ps_filing_date = models.DateField(
        verbose_name='公安备案日期',
        null=True,
        blank=True,
        help_text='公安联网备案通过日期',
        db_comment='公安备案日期',
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name='启用状态',
        help_text='是否纳入资产管理范围',
        db_comment='启用状态：True启用/False禁用',
    )
    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='domains',
        verbose_name='所属公司',
        help_text='域名归属的公司主体',
        db_comment='归属公司主体ID，关联company表',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = '域名'
        verbose_name_plural = verbose_name
        ordering = ['-expire_time']
        db_table_comment = '域名资产表，记录注册域名及SSL证书信息'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return self.domain_name


# =============================================================================
# DNS 解析记录
# =============================================================================


class DnsRecord(DbAuditModel, DbUuidModel):
    """域名 DNS 解析记录，记录每个域名的解析配置。"""

    domain = models.ForeignKey(
        to=Domain,
        on_delete=models.CASCADE,
        related_name='dns_records',
        verbose_name='所属域名',
        help_text='该解析记录归属的域名',
        db_comment='归属域名ID，关联domain表',
    )
    record_type = models.CharField(
        max_length=16,
        choices=DnsRecordTypeChoices,
        verbose_name='记录类型',
        help_text='DNS 记录类型：A/AAAA/CNAME/MX/TXT/NS/SRV/CAA',
        db_comment='DNS记录类型枚举值',
    )
    host = models.CharField(
        max_length=256,
        verbose_name='主机记录',
        help_text='主机记录前缀，如 @、www、mail',
        db_comment='主机记录前缀',
    )
    value = models.TextField(
        verbose_name='记录值',
        help_text='解析目标，A记录为IP、CNAME为目标域名、MX为邮件服务器地址等',
        db_comment='解析记录值',
    )
    ttl = models.PositiveIntegerField(
        default=600,
        verbose_name='TTL（秒）',
        help_text='生存时间，默认 600 秒',
        db_comment='TTL生存时间（秒）',
    )
    priority = models.PositiveSmallIntegerField(
        verbose_name='优先级',
        null=True,
        blank=True,
        help_text='MX/SRV 记录的优先级，值越小优先级越高',
        db_comment='MX/SRV记录优先级',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='启用状态',
        help_text='解析记录是否生效',
        db_comment='启用状态：True启用/False禁用',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = 'DNS 解析记录'
        verbose_name_plural = verbose_name
        ordering = ['domain', 'record_type', 'host']
        db_table_comment = '域名DNS解析记录表，存储每个域名的解析配置'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f'{self.domain.domain_name} - {self.host} {self.record_type} → {self.value}'


# =============================================================================
# 本地物理服务器
# =============================================================================


class LocalServer(DbAuditModel, DbUuidModel):
    """本地物理服务器（裸金属），记录机房物理机信息。

    硬件配置通过 JSON 字段详细记录 CPU、内存、硬盘的插槽级配置：
    - cpus: 每颗物理 CPU 的型号、核心数、线程数、主频
    - memories: 每条内存的容量、类型、频率、插槽位置
    - disks: 每块硬盘的容量、类型（SSD/HDD/NVMe）、接口、插槽位置
    """

    name = models.CharField(
        max_length=128,
        verbose_name='主机名称',
        help_text='物理服务器显示名称，如 DC-Rack01-U10',
        db_comment='物理服务器显示名称',
    )
    hostname = models.CharField(
        max_length=256,
        verbose_name='主机名',
        null=True,
        blank=True,
        help_text='操作系统 hostname',
        db_comment='操作系统主机名',
    )
    ip_address = models.GenericIPAddressField(
        verbose_name='管理 IP',
        help_text='主管理网口 IPv4 地址',
        db_comment='管理口IP地址',
    )
    mac_address = models.CharField(
        max_length=32,
        verbose_name='MAC 地址',
        null=True,
        blank=True,
        help_text='管理网口 MAC 地址，格式 xx:xx:xx:xx:xx:xx',
        db_comment='管理口MAC地址',
    )
    os_type = models.CharField(
        max_length=32,
        choices=ServerOSTypeChoices,
        default=ServerOSTypeChoices.LINUX,
        verbose_name='操作系统类型',
        help_text='服务器操作系统类型枚举',
        db_comment='操作系统类型枚举值',
    )
    os_version = models.CharField(
        max_length=64,
        verbose_name='操作系统版本',
        null=True,
        blank=True,
        help_text='操作系统详细版本号',
        db_comment='操作系统版本号',
    )

    # --- CPU 配置 ---
    cpu_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='CPU 数量',
        help_text='物理 CPU 颗数',
        db_comment='物理CPU颗数',
    )
    cpu_model = models.CharField(
        max_length=128,
        verbose_name='CPU 型号',
        null=True,
        blank=True,
        help_text='CPU 型号，如 Intel Xeon Gold 6248R',
        db_comment='CPU型号',
    )
    cpu_total_cores = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='总核心数',
        help_text='所有 CPU 物理核心总数',
        db_comment='所有CPU物理核心总数',
    )
    cpu_total_threads = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='总线程数',
        help_text='所有 CPU 逻辑线程总数（含超线程）',
        db_comment='所有CPU逻辑线程总数',
    )

    # --- 内存配置 ---
    memory_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='内存条数量',
        help_text='物理内存条根数',
        db_comment='物理内存条根数',
    )
    memory_total = models.PositiveIntegerField(
        default=0,
        verbose_name='内存总量（GB）',
        help_text='所有内存条合计容量，单位 GB',
        db_comment='内存总量（GB）',
    )
    memory_type = models.CharField(
        max_length=32,
        verbose_name='内存类型',
        null=True,
        blank=True,
        help_text='内存类型，如 DDR4/DDR5',
        db_comment='内存类型',
    )
    memory_frequency = models.PositiveIntegerField(
        verbose_name='内存频率（MHz）',
        null=True,
        blank=True,
        help_text='内存工作频率，如 3200',
        db_comment='内存频率（MHz）',
    )

    # --- 硬盘配置 ---
    disk_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='硬盘数量',
        help_text='物理硬盘块数',
        db_comment='物理硬盘块数',
    )
    disk_total = models.PositiveIntegerField(
        default=0,
        verbose_name='磁盘总量（GB）',
        help_text='所有硬盘合计容量，单位 GB',
        db_comment='磁盘总容量（GB）',
    )

    # --- 详细硬件清单（JSON） ---
    cpu_detail = models.JSONField(
        verbose_name='CPU 详细配置',
        null=True,
        blank=True,
        default=list,
        validators=[PydanticListValidator('apps.asset.structs.CpuDetailItem')],
        help_text='每颗 CPU 的详细配置列表，结构定义见 apps.asset.structs.CpuDetailItem',
        db_comment='CPU详细配置JSON列表',
    )
    memory_detail = models.JSONField(
        verbose_name='内存详细配置',
        null=True,
        blank=True,
        default=list,
        validators=[PydanticListValidator('apps.asset.structs.MemoryDetailItem')],
        help_text='每条内存的详细配置列表，结构定义见 apps.asset.structs.MemoryDetailItem',
        db_comment='内存详细配置JSON列表',
    )
    disk_detail = models.JSONField(
        verbose_name='硬盘详细配置',
        null=True,
        blank=True,
        default=list,
        validators=[PydanticListValidator('apps.asset.structs.DiskDetailItem')],
        help_text='每块硬盘的详细配置列表，结构定义见 apps.asset.structs.DiskDetailItem',
        db_comment='硬盘详细配置JSON列表',
    )

    # --- 位置与维保 ---
    rack_location = models.CharField(
        max_length=128,
        verbose_name='机架位置',
        null=True,
        blank=True,
        help_text='机房机架位置，如 DC-A-01-U10',
        db_comment='机房机架物理位置',
    )
    serial_number = models.CharField(
        max_length=128,
        verbose_name='序列号',
        null=True,
        blank=True,
        help_text='硬件序列号（SN码）',
        db_comment='硬件序列号',
    )
    purchase_date = models.DateField(
        verbose_name='采购日期',
        null=True,
        blank=True,
        help_text='硬件采购日期',
        db_comment='硬件采购日期',
    )
    warranty_expire = models.DateField(
        verbose_name='维保到期',
        null=True,
        blank=True,
        help_text='硬件维保到期日期',
        db_comment='维保到期日期',
    )
    status = models.CharField(
        max_length=32,
        choices=ServerStatusChoices,
        default=ServerStatusChoices.RUNNING,
        verbose_name='运行状态',
        help_text='服务器当前运行状态',
        db_comment='服务器运行状态枚举值',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='启用状态',
        help_text='是否纳入资产管理范围',
        db_comment='启用状态：True启用/False禁用',
    )
    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_servers',
        verbose_name='所属公司',
        help_text='资产归属的公司主体',
        db_comment='归属公司主体ID，关联company表',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = '本地服务器'
        verbose_name_plural = verbose_name
        ordering = ['-created_time']
        db_table_comment = '本地物理服务器资产表，记录机房物理机信息'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f'{self.name} ({self.ip_address})'


# =============================================================================
# 本地虚拟主机
# =============================================================================


class LocalVM(DbAuditModel, DbUuidModel):
    """本地虚拟主机，运行在物理服务器上的虚拟机实例。"""

    name = models.CharField(
        max_length=128,
        verbose_name='虚拟机名称',
        help_text='虚拟机显示名称，如 K8s-Node-01',
        db_comment='虚拟机显示名称',
    )
    host_server = models.ForeignKey(
        to=LocalServer,
        on_delete=models.PROTECT,
        related_name='virtual_machines',
        verbose_name='宿主机',
        help_text='运行该虚拟机的物理宿主机',
        db_comment='宿主机ID，关联localserver表',
    )
    ip_address = models.GenericIPAddressField(
        verbose_name='IP 地址',
        null=True,
        blank=True,
        help_text='虚拟机 IPv4 地址',
        db_comment='虚拟机IP地址',
    )
    mac_address = models.CharField(
        max_length=32,
        verbose_name='MAC 地址',
        null=True,
        blank=True,
        help_text='虚拟网卡 MAC 地址',
        db_comment='虚拟网卡MAC地址',
    )
    os_type = models.CharField(
        max_length=32,
        choices=ServerOSTypeChoices,
        default=ServerOSTypeChoices.LINUX,
        verbose_name='操作系统类型',
        help_text='虚拟机操作系统类型枚举',
        db_comment='操作系统类型枚举值',
    )
    os_version = models.CharField(
        max_length=64,
        verbose_name='操作系统版本',
        null=True,
        blank=True,
        help_text='操作系统详细版本号',
        db_comment='操作系统版本号',
    )
    cpu = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='vCPU 核数',
        help_text='分配虚拟 CPU 核心数',
        db_comment='vCPU核数',
    )
    memory = models.PositiveIntegerField(
        default=0,
        verbose_name='内存（GB）',
        help_text='分配内存大小，单位 GB',
        db_comment='分配内存（GB）',
    )
    disk_size = models.PositiveIntegerField(
        default=0,
        verbose_name='磁盘容量（GB）',
        help_text='分配磁盘容量，单位 GB',
        db_comment='分配磁盘容量（GB）',
    )
    hypervisor = models.CharField(
        max_length=32,
        choices=HypervisorTypeChoices,
        default=HypervisorTypeChoices.VMWARE,
        verbose_name='虚拟化平台',
        help_text='虚拟化平台类型枚举',
        db_comment='虚拟化平台类型枚举值',
    )
    vm_id = models.CharField(
        max_length=128,
        verbose_name='虚拟机 ID',
        null=True,
        blank=True,
        help_text='虚拟化平台内部虚拟机标识，如 vSphere vm-xxx',
        db_comment='虚拟化平台内部VM标识',
    )
    status = models.CharField(
        max_length=32,
        choices=ServerStatusChoices,
        default=ServerStatusChoices.RUNNING,
        verbose_name='运行状态',
        help_text='虚拟机当前运行状态',
        db_comment='虚拟机运行状态枚举值',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='启用状态',
        help_text='是否纳入资产管理范围',
        db_comment='启用状态：True启用/False禁用',
    )
    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='local_vms',
        verbose_name='所属公司',
        help_text='资产归属的公司主体',
        db_comment='归属公司主体ID，关联company表',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = '本地虚拟主机'
        verbose_name_plural = verbose_name
        ordering = ['host_server', '-created_time']
        db_table_comment = '本地虚拟主机资产表，记录物理服务器上的虚拟机实例'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f'{self.name} ({self.host_server.name})'
