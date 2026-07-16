"""云平台管理应用的模型定义。"""

from datetime import date, timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.cloud_platform.choices import (
    AgentStatusChoices,
    CredentialTypeChoices,
    PlatformTypeChoices,
    SyncResourceTypeChoices,
    SyncStatusChoices,
    SyncTriggerTypeChoices,
)
from apps.common.core.models import DbAuditModel, DbUuidModel
from apps.common.fields.encrypted import EncryptedTextField
from apps.company.models import Company


class CloudPlatform(DbAuditModel, DbUuidModel):
    """云平台实例，记录不同云服务商或基础设施的连接信息。

    支持公有云（腾讯云/阿里云/AWS/Azure/华为云）、私有化部署（vCenter）、
    以及特定服务商（美橙等）。每个平台可关联多个凭据记录。
    """

    name = models.CharField(
        max_length=128,
        verbose_name=_('平台名称'),
        unique=True,
        help_text=_('自定义平台实例名称，如：生产环境-腾讯云'),
        db_comment='平台实例名称，唯一',
    )
    platform_type = models.CharField(
        max_length=32,
        choices=PlatformTypeChoices,
        default=PlatformTypeChoices.TENCENT_CLOUD,
        verbose_name=_('平台类型'),
        help_text=_('云平台类型枚举：腾讯云/阿里云/AWS/Azure/华为云/vCenter/美橙/其他'),
        db_comment='云平台类型枚举值',
    )
    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='platforms',
        verbose_name=_('所属公司'),
        help_text=_('平台归属的公司主体（个人注册或无公司归属可不填）'),
        db_comment='平台归属的公司主体ID，关联company表',
    )
    endpoint = models.CharField(
        max_length=512,
        verbose_name=_('API 端点'),
        null=True,
        blank=True,
        help_text=_('API 访问地址，如 https://cvm.tencentcloudapi.com'),
        db_comment='API访问地址',
    )
    region = models.CharField(
        max_length=128,
        verbose_name=_('默认区域'),
        null=True,
        blank=True,
        help_text=_('默认区域标识，如 ap-guangzhou'),
        db_comment='默认区域标识',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('启用状态'),
        help_text=_('平台是否启用，禁用后不可用于新建凭据'),
        db_comment='平台启用状态：True启用/False禁用',
    )

    # --- 账户余额字段 ---
    account_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        blank=True,
        verbose_name=_('账户余额（元）'),
        help_text=_('云平台账户实时余额，仅支持余额查询的平台有效，单位为元'),
        db_comment='云平台账户实时余额（元），不支持余额查询的平台为0',
    )
    balance_updated_time = models.DateTimeField(
        verbose_name=_('余额更新时间'),
        null=True,
        blank=True,
        help_text=_('最近一次余额查询的时间，为空表示从未查询'),
        db_comment='最近一次余额查询时间',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = _('云平台实例')
        verbose_name_plural = verbose_name
        ordering = ['-created_time']
        db_table_comment = _('云平台实例表，记录不同云服务商或基础设施的连接信息')

    def __str__(self) -> str:
        """返回平台名称和类型的组合标识。"""
        return f'{self.name} ({self.get_platform_type_display()})'


class Credential(DbAuditModel, DbUuidModel):
    """云平台认证凭据，支持多种认证方式。

    凭据类型：
    - access_key: 适用于公有云 ACCESS_KEY/SECRET_KEY 密钥对
    - password: 适用于用户名/密码登录（vCenter、美橙等），可配合 email 字段使用
    - api_token: 适用于 API Token 认证

    扩展机制：
    - email 字段：满足美橙等需要邮箱的场景
    - extra_data JSON 字段：存储任意额外的键值对，适配不同平台的个性化认证需求
    """

    platform = models.ForeignKey(
        to=CloudPlatform,
        on_delete=models.CASCADE,
        related_name='credentials',
        verbose_name=_('所属平台'),
        help_text=_('该凭据归属的云平台实例'),
        db_comment='凭据归属的云平台实例ID，关联cloudplatform表',
    )
    credential_type = models.CharField(
        max_length=32,
        choices=CredentialTypeChoices,
        verbose_name=_('凭据类型'),
        help_text=_('凭据类型枚举：access_key/password/api_token'),
        db_comment='凭据类型枚举值',
    )
    credential_name = models.CharField(
        max_length=128,
        verbose_name=_('凭据名称'),
        help_text=_('自定义凭据标识，如：运维账号'),
        db_comment='自定义凭据标识名称',
    )

    # --- Access Key 类型字段 ---
    access_key = EncryptedTextField(
        verbose_name=_('Access Key ID'),
        null=True,
        blank=True,
        default='',
        help_text=_('云平台 Access Key ID（加密存储）'),
        db_comment='Access Key ID（加密存储）',
    )
    access_secret = EncryptedTextField(
        verbose_name=_('Secret Access Key'),
        null=True,
        blank=True,
        default='',
        help_text=_('云平台 Secret Access Key（加密存储）'),
        db_comment='Secret Access Key（加密存储）',
    )

    # --- 用户名密码类型字段 ---
    username = models.CharField(
        max_length=128,
        verbose_name=_('用户名'),
        null=True,
        blank=True,
        help_text=_('登录用户名'),
        db_comment='登录用户名',
    )
    password = EncryptedTextField(
        verbose_name=_('密码'),
        null=True,
        blank=True,
        default='',
        help_text=_('登录密码（加密存储）'),
        db_comment='登录密码（加密存储）',
    )
    email = models.EmailField(
        verbose_name=_('邮箱'),
        null=True,
        blank=True,
        help_text=_('关联邮箱（美橙等部分服务商认证需要）'),
        db_comment='关联邮箱地址',
    )

    # --- API Token 类型字段 ---
    api_token = EncryptedTextField(
        verbose_name=_('API Token'),
        null=True,
        blank=True,
        default='',
        help_text=_('API 访问令牌（加密存储）'),
        db_comment='API访问令牌（加密存储）',
    )
    token_expire_time = models.DateTimeField(
        verbose_name=_('Token 过期时间'),
        null=True,
        blank=True,
        help_text=_('Token 过期时间，为空表示永不过期'),
        db_comment='Token过期时间，为空表示永不过期',
    )

    # --- 通用字段 ---
    extra_data = models.JSONField(
        verbose_name=_('扩展数据'),
        null=True,
        blank=True,
        default=dict,
        help_text=_('扩展 JSON 字段，存储不同平台的个性化认证键值对'),
        db_comment='扩展JSON键值对，适配个性化认证需求',
    )
    remark = models.TextField(
        verbose_name=_('备注'),
        null=True,
        blank=True,
        help_text=_('凭据用途说明'),
        db_comment='凭据用途说明',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('启用状态'),
        help_text=_('凭据是否启用，禁用后不可用于API调用'),
        db_comment='凭据启用状态：True启用/False禁用',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = _('云平台凭据')
        verbose_name_plural = verbose_name
        ordering = ['platform', '-created_time']
        db_table_comment = _('云平台凭据表，存储不同认证方式的加密凭据信息')

    def __str__(self) -> str:
        """返回凭据所属平台、名称和类型的组合标识。"""
        return f'{self.platform.name} - {self.credential_name} ({self.get_credential_type_display()})'


class AccountBalance(DbAuditModel, DbUuidModel):
    """云平台账户余额每日快照。

    按日期线性存储每个平台的余额历史，自动保留最近 30 天数据。
    每次调用 refresh-balance 接口时创建当天的快照记录，
    并清理超过 30 天的旧记录。

    约束：(platform, record_date) 唯一，同一天内多次刷新会更新同一条记录。
    """

    platform = models.ForeignKey(
        to=CloudPlatform,
        on_delete=models.CASCADE,
        related_name='balance_records',
        verbose_name='云平台',
        help_text='所属云平台实例',
        db_comment='云平台实例ID，关联cloudplatform表',
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='余额（元）',
        help_text='当日账户余额',
        db_comment='当日账户余额（元）',
    )
    record_date = models.DateField(
        verbose_name='记录日期',
        help_text='余额快照对应的日期',
        db_comment='余额快照日期',
    )

    class Meta:
        """元数据配置。"""

        verbose_name = '账户余额记录'
        verbose_name_plural = verbose_name
        ordering = ['platform', '-record_date']
        db_table_comment = '云平台账户余额每日快照表，按天存储最近30天数据'
        constraints = [
            models.UniqueConstraint(
                fields=['platform', 'record_date'],
                name='unique_platform_balance_date',
            ),
        ]

    def __str__(self) -> str:
        """返回平台名称和日期的组合标识。"""
        return f'{self.platform.name} - {self.record_date}: ¥{self.balance}'

    @classmethod
    def cleanup_old_records(cls, platform_id: str, keep_days: int = 30) -> int:
        """清理指定平台超过保留天数的旧余额记录。

        Args:
            platform_id: 云平台主键。
            keep_days: 保留天数，默认 30。

        Returns:
            删除的记录数。
        """
        cutoff = date.today() - timedelta(days=keep_days)
        deleted, _ = cls.objects.filter(
            platform_id=platform_id,
            record_date__lt=cutoff,
        ).delete()
        return deleted


class SyncRecord(DbAuditModel, DbUuidModel):
    """同步记录，记录每次同步任务的整体执行情况。

    每次同步任务可能包含多种资源类型（服务器/域名/DNS记录/余额），
    由多个 Agent 分工执行，各 Agent 的执行详情见 SyncAgentLog。
    """

    platform = models.ForeignKey(
        to=CloudPlatform,
        on_delete=models.CASCADE,
        related_name='sync_records',
        verbose_name=_('云平台'),
        help_text=_('所属云平台实例'),
        db_comment='所属云平台实例ID，关联cloud_platform表',
    )
    sync_type = models.CharField(
        max_length=32,
        choices=SyncTriggerTypeChoices,
        verbose_name=_('触发类型'),
        help_text=_('同步任务的触发方式：手动触发/定时触发/Webhook 触发'),
        db_comment='同步触发类型',
    )
    status = models.CharField(
        max_length=32,
        choices=SyncStatusChoices,
        default=SyncStatusChoices.PENDING,
        verbose_name=_('同步状态'),
        help_text=_('同步任务当前状态：等待中/运行中/已完成/部分成功/失败/已取消'),
        db_comment='同步任务状态',
    )
    resources = models.JSONField(
        default=list,
        verbose_name=_('同步资源'),
        help_text=_('本次同步包含的资源类型列表，如：["server", "domain"]'),
        db_comment='同步资源类型列表（JSON数组）',
    )
    total_created = models.IntegerField(
        default=0,
        verbose_name=_('新建数量'),
        help_text=_('本次同步新建的资源数量'),
        db_comment='新建资源数量',
    )
    total_updated = models.IntegerField(
        default=0,
        verbose_name=_('更新数量'),
        help_text=_('本次同步更新的资源数量'),
        db_comment='更新资源数量',
    )
    total_terminated = models.IntegerField(
        default=0,
        verbose_name=_('终止数量'),
        help_text=_('本次同步发现已终止/删除的资源数量'),
        db_comment='终止资源数量',
    )
    total_errors = models.IntegerField(
        default=0,
        verbose_name=_('错误数量'),
        help_text=_('本次同步累计错误数量'),
        db_comment='累计错误数量',
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('开始时间'),
        help_text=_('同步任务开始执行的时间'),
        db_comment='同步开始时间',
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('结束时间'),
        help_text=_('同步任务执行结束的时间'),
        db_comment='同步结束时间',
    )
    error_detail = models.JSONField(
        default=list,
        verbose_name=_('错误详情'),
        help_text=_('同步过程中的错误详情列表，每项含 item 和 error 字段'),
        db_comment='错误详情列表（JSON数组）',
    )

    class Meta:
        """元数据配置。"""

        ordering = ['-created_time']
        db_table_comment = '同步记录表，记录每次同步任务的整体执行情况'
        verbose_name = _('同步记录')
        verbose_name_plural = _('同步记录')

    def __str__(self) -> str:
        """返回平台名称、状态和创建时间的组合标识。"""
        return f'{self.platform.name} - {self.get_status_display()} ({self.created_time})'


class SyncAgentLog(DbAuditModel, DbUuidModel):
    """同步 Agent 日志，记录单个 Agent 子任务的执行详情。

    每个 SyncRecord 包含多个 Agent 子任务，每个 Agent 负责一种资源类型的同步。
    各 Agent 间状态隔离，支持独立重试。
    """

    sync_record = models.ForeignKey(
        to=SyncRecord,
        on_delete=models.CASCADE,
        related_name='agent_logs',
        verbose_name=_('同步记录'),
        help_text=_('所属的同步记录'),
        db_comment='所属同步记录ID，关联sync_record表',
    )
    agent_name = models.CharField(
        max_length=128,
        verbose_name=_('Agent 名称'),
        help_text=_('执行同步的 Agent 或子模块名称，如 tencent-server'),
        db_comment='Agent/子模块名称',
    )
    resource_type = models.CharField(
        max_length=32,
        choices=SyncResourceTypeChoices,
        verbose_name=_('资源类型'),
        help_text=_('Agent 负责同步的资源类型'),
        db_comment='同步资源类型',
    )
    status = models.CharField(
        max_length=32,
        choices=AgentStatusChoices,
        default=AgentStatusChoices.PENDING,
        verbose_name=_('执行状态'),
        help_text=_('Agent 子任务的执行状态'),
        db_comment='Agent执行状态',
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('开始时间'),
        help_text=_('Agent 子任务开始执行的时间'),
        db_comment='Agent开始执行时间',
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('结束时间'),
        help_text=_('Agent 子任务执行结束的时间'),
        db_comment='Agent结束执行时间',
    )
    log = models.TextField(
        blank=True,
        default='',
        verbose_name=_('执行日志'),
        help_text=_('Agent 执行的详细日志输出'),
        db_comment='Agent详细执行日志',
    )
    created_count = models.IntegerField(
        default=0,
        verbose_name=_('新建数量'),
        help_text=_('Agent 新建的资源数量'),
        db_comment='Agent新建资源数量',
    )
    updated_count = models.IntegerField(
        default=0,
        verbose_name=_('更新数量'),
        help_text=_('Agent 更新的资源数量'),
        db_comment='Agent更新资源数量',
    )
    terminated_count = models.IntegerField(
        default=0,
        verbose_name=_('终止数量'),
        help_text=_('Agent 发现已终止/删除的资源数量'),
        db_comment='Agent终止资源数量',
    )
    error_count = models.IntegerField(
        default=0,
        verbose_name=_('错误数量'),
        help_text=_('Agent 子任务的错误数量'),
        db_comment='Agent错误数量',
    )
    error_detail = models.JSONField(
        default=list,
        verbose_name=_('错误详情'),
        help_text=_('Agent 子任务的错误详情列表'),
        db_comment='Agent错误详情列表（JSON数组）',
    )
    retry_count = models.IntegerField(
        default=0,
        verbose_name=_('重试次数'),
        help_text=_('Agent 子任务的重试次数'),
        db_comment='Agent重试次数',
    )
    extra_data = models.JSONField(
        default=dict,
        verbose_name=_('扩展数据'),
        help_text=_('Agent 特定的扩展数据，如进度信息、中间状态等'),
        db_comment='Agent扩展数据（JSON对象）',
    )

    class Meta:
        """元数据配置。"""

        ordering = ['created_time']
        db_table_comment = '同步Agent执行日志表，记录每个子任务的执行详情'
        verbose_name = _('同步Agent日志')
        verbose_name_plural = _('同步Agent日志')
        unique_together = ('sync_record', 'agent_name')

    def __str__(self) -> str:
        """返回 Agent 名称、状态和所属同步记录的标识。"""
        return f'{self.agent_name} - {self.get_status_display()} ({self.sync_record_id})'
