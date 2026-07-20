"""域名管理应用的模型定义。

包含域名资产相关的四大模型：
- Domain: �名名资产
- DnsRecord: DNS 解析记录
- Filing: 备案信息（ICP + 公安）
- SslCertificate: SSL 证书

所有模型继承 DbAuditModel + DbUuidModel，支持导入导出和审计追溯。
从 apps.asset 迁移而来，数据库表名保持不变（asset_*）以兼容历史数据。
"""

from django.db import models

from apps.cloud_platform.models import CloudPlatform
from apps.common.core.models import DbAuditModel, DbUuidModel, upload_directory_path
from apps.common.fields.encrypted import EncryptedTextField
from apps.company.models import Company
from apps.domain.choices import (
    DnsRecordTypeChoices,
    DomainStatusChoices,
    IcpCheckStatusChoices,
    IcpFilingStatusChoices,
)

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
    ssl_certificate = models.ForeignKey(
        to='SslCertificate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='domains',
        verbose_name='SSL 证书',
        help_text='关联的 SSL 证书记录，相同证书共用一条记录',
        db_comment='关联SSL证书记录ID',
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
        db_table = 'asset_domain'
        db_table_comment = '域名资产表，记录注册域名及SSL证书信息'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return self.domain_name


# =============================================================================
# 备案信息（统一模型）
# =============================================================================


class Filing(DbAuditModel, DbUuidModel):
    """备案信息统一模型，同时管理 ICP 备案（工信部备案）和公安备案。

    每个域名对应一条备案记录，通过 icp_* 和 ps_* 前缀字段分别管理两类备案，
    确保字段、状态及校验逻辑完全解耦。支持 ICP 预检测首页页脚备案号悬挂。
    """

    domain = models.OneToOneField(
        to=Domain,
        on_delete=models.CASCADE,
        related_name='filing',
        verbose_name='关联域名',
        help_text='该备案记录关联的域名',
        db_comment='关联域名ID，一对一',
    )

    # ---- ICP 备案字段 ----
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
    icp_unit_name = models.CharField(
        max_length=256,
        verbose_name='ICP 备案主体',
        null=True,
        blank=True,
        help_text='ICP 备案主体名称（单位/个人名称）',
        db_comment='ICP备案主体名称',
    )
    icp_status = models.CharField(
        max_length=32,
        choices=IcpFilingStatusChoices,
        default=IcpFilingStatusChoices.NOT_FILED,
        verbose_name='ICP 备案状态',
        help_text='ICP 备案当前状态：未备案/已备案/待人工确认/变更中',
        db_comment='ICP备案状态枚举值',
    )
    icp_check_status = models.CharField(
        max_length=32,
        choices=IcpCheckStatusChoices,
        default=IcpCheckStatusChoices.NOT_CHECKED,
        verbose_name='ICP 预检测状态',
        help_text='首页悬挂备案号预检测结果',
        db_comment='ICP预检测状态枚举值',
    )
    icp_has_www_record = models.BooleanField(
        default=False,
        verbose_name='有www解析',
        help_text='域名是否存在 www 子域名的 DNS 解析记录',
        db_comment='是否存在www解析记录',
    )
    icp_footer_content = models.TextField(
        verbose_name='页脚内容',
        null=True,
        blank=True,
        help_text='首页页脚区域抓取到的文本内容（预检测时填充）',
        db_comment='首页页脚文本内容',
    )
    icp_check_conclusion = models.TextField(
        verbose_name='检测结论',
        null=True,
        blank=True,
        help_text='预检测的详细结论描述',
        db_comment='预检测结论描述',
    )
    icp_check_time = models.DateTimeField(
        verbose_name='检测时间',
        null=True,
        blank=True,
        help_text='最近一次预检测执行时间',
        db_comment='最近预检测时间',
    )

    # ---- 公安备案字段 ----
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
    ps_unit_name = models.CharField(
        max_length=256,
        verbose_name='公安备案主体',
        null=True,
        blank=True,
        help_text='公安备案主体名称',
        db_comment='公安备案主体名称',
    )
    ps_public_security_agency = models.CharField(
        max_length=128,
        verbose_name='备案公安机关',
        null=True,
        blank=True,
        help_text='受理备案的公安机关名称',
        db_comment='备案公安机关名称',
    )
    ps_status = models.CharField(
        max_length=32,
        choices=IcpFilingStatusChoices,
        default=IcpFilingStatusChoices.NOT_FILED,
        verbose_name='公安备案状态',
        help_text='公安备案当前状态：未备案/已备案/待人工确认',
        db_comment='公安备案状态枚举值',
    )

    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='filings',
        verbose_name='所属公司',
        help_text='备案主体归属的公司（冗余字段，用于筛选）',
        db_comment='归属公司主体ID',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = '备案信息'
        verbose_name_plural = verbose_name
        ordering = ['-created_time']
        db_table = 'asset_filing'
        db_table_comment = '备案信息统一表，同时存储ICP备案与公安备案，通过 icp_*/ps_* 前缀字段区分'

    def __str__(self) -> str:
        """返回字符串表示，包含域名和备案号。"""
        parts = [self.domain.domain_name]
        if self.icp_number:
            parts.append(f'ICP:{self.icp_number}')
        if self.ps_filing_number:
            parts.append(f'公安:{self.ps_filing_number}')
        return ' '.join(parts)


# =============================================================================
# SSL 证书
# =============================================================================


class SslCertificate(DbAuditModel, DbUuidModel):
    """SSL 证书详细信息，相同证书（SHA256 指纹相同）只存一条。

    多个 Domain 通过 ForeignKey 关联到同一条 SslCertificate 记录，
    避免通配符/SAN 证书被重复存储。由预检测流程和定时任务自动填充。
    """

    # ---- 证书唯一标识 ----
    fingerprint = models.CharField(
        max_length=128,
        unique=True,
        verbose_name='证书指纹',
        help_text='SHA256 指纹，用于判断证书是否完全一致（去重依据）',
        db_comment='SHA256指纹，唯一标识',
    )

    # ---- 主体信息（Subject）----
    subject_cn = models.CharField(
        max_length=256,
        verbose_name='主体通用名',
        null=True,
        blank=True,
        help_text='证书主体 Common Name，通常为域名',
        db_comment='主体CN',
    )
    subject_o = models.CharField(
        max_length=256,
        verbose_name='主体组织',
        null=True,
        blank=True,
        help_text='证书主体 Organization',
        db_comment='主体O',
    )
    subject_ou = models.CharField(
        max_length=256,
        verbose_name='主体组织单元',
        null=True,
        blank=True,
        help_text='证书主体 Organizational Unit',
        db_comment='主体OU',
    )

    # ---- 颁发者信息（Issuer）----
    issuer_cn = models.CharField(
        max_length=256,
        verbose_name='颁发机构通用名',
        null=True,
        blank=True,
        help_text='颁发机构 Common Name',
        db_comment='颁发机构CN',
    )
    issuer_o = models.CharField(
        max_length=256,
        verbose_name='颁发机构组织',
        null=True,
        blank=True,
        help_text='颁发机构 Organization',
        db_comment='颁发机构O',
    )

    # ---- 证书属性 ----
    serial_number = models.CharField(
        max_length=128,
        verbose_name='序列号',
        null=True,
        blank=True,
        help_text='证书唯一序列号（十六进制）',
        db_comment='证书序列号',
    )
    signature_algorithm = models.CharField(
        max_length=64,
        verbose_name='签名算法',
        null=True,
        blank=True,
        help_text='证书签名哈希算法，如 sha256',
        db_comment='签名算法',
    )
    not_before = models.DateTimeField(
        verbose_name='有效期起始',
        null=True,
        blank=True,
        help_text='证书生效时间（UTC）',
        db_comment='证书有效期起始',
    )
    not_after = models.DateTimeField(
        verbose_name='有效期结束',
        null=True,
        blank=True,
        help_text='证书到期时间（UTC）',
        db_comment='证书有效期结束',
    )
    san_domains = models.JSONField(
        verbose_name='备用域名',
        default=list,
        blank=True,
        help_text='Subject Alternative Names 列表（证书覆盖的所有域名）',
        db_comment='SAN域名列表',
    )
    is_valid = models.BooleanField(
        default=False,
        verbose_name='是否有效',
        help_text='检测时证书是否在有效期内',
        db_comment='证书是否有效',
    )
    check_time = models.DateTimeField(
        verbose_name='检测时间',
        null=True,
        blank=True,
        help_text='最近一次 SSL 证书检测时间',
        db_comment='最近检测时间',
    )

    # ---- PEM 格式证书文件（用于部署）----
    certificate_pem = models.TextField(
        verbose_name='终端证书',
        null=True,
        blank=True,
        help_text='终端证书 PEM 格式内容（自动检测填充）',
        db_comment='终端证书PEM',
    )
    intermediate_pem = models.TextField(
        verbose_name='中间证书',
        null=True,
        blank=True,
        help_text='中间证书链 PEM 格式内容（自动检测填充，可能包含多张中间证书）',
        db_comment='中间证书链PEM',
    )
    private_key_pem = EncryptedTextField(
        verbose_name='私钥',
        null=True,
        blank=True,
        help_text='私钥 PEM 格式内容（加密存储，需手动上传，无法自动检测）',
        db_comment='私钥PEM（加密）',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = 'SSL 证书'
        verbose_name_plural = verbose_name
        ordering = ['-created_time']
        db_table = 'asset_sslcertificate'
        db_table_comment = 'SSL证书详细信息表，相同证书（指纹去重）只存一条，被多个域名关联'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f'SSL: {self.subject_cn or "未知"} ({self.serial_number or "?"})'


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
    is_ssl_enabled = models.BooleanField(
        default=False,
        verbose_name='SSL 证书',
        help_text='该子域名是否支持 HTTPS（由 SSL 定时检测自动更新）',
        db_comment='是否支持HTTPS',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = 'DNS 解析记录'
        verbose_name_plural = verbose_name
        ordering = ['domain', 'record_type', 'host']
        db_table = 'asset_dnsrecord'
        db_table_comment = '域名DNS解析记录表，存储每个域名的解析配置'

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f'{self.domain.domain_name} - {self.host} {self.record_type} → {self.value}'
