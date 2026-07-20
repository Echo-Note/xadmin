"""资产管理应用的模型定义。

包含三大资产类型（域名相关模型已迁移至 apps.domain）：
- CloudServer: 云服务器资产
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
    HypervisorTypeChoices,
    ServerOSTypeChoices,
    ServerStatusChoices,
)
from apps.cloud_platform.models import CloudPlatform
from apps.common.core.models import DbAuditModel, DbUuidModel
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
