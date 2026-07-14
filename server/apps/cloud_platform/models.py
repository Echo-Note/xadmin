"""云平台管理应用的模型定义。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel
from apps.common.fields.encrypted import EncryptedTextField
from apps.company.models import Company


class CloudPlatform(DbAuditModel):
    """云平台实例，记录不同云服务商或基础设施的连接信息。

    支持公有云（腾讯云/阿里云/AWS/Azure/华为云）、私有化部署（vCenter）、
    以及特定服务商（美橙等）。每个平台可关联多个凭据记录。
    """

    class PlatformTypeChoices(models.TextChoices):
        """云平台类型枚举。"""

        TENCENT_CLOUD = "tencent", _("腾讯云")
        ALI_CLOUD = "aliyun", _("阿里云")
        AWS = "aws", _("AWS")
        AZURE = "azure", _("Azure")
        HUAWEI_CLOUD = "huawei", _("华为云")
        VCENTER = "vcenter", _("vCenter")
        MEICHENG = "meicheng", _("美橙")
        OTHER = "other", _("其他")

    name = models.CharField(
        max_length=128, verbose_name=_("平台名称"), unique=True,
        help_text=_("自定义平台实例名称，如：生产环境-腾讯云"),
    )
    platform_type = models.CharField(
        max_length=32,
        choices=PlatformTypeChoices,
        default=PlatformTypeChoices.TENCENT_CLOUD,
        verbose_name=_("平台类型"),
    )
    company = models.ForeignKey(
        to=Company,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="platforms",
        verbose_name=_("所属公司"),
        help_text=_("平台归属的公司主体（个人注册或无公司归属可不填）"),
    )
    endpoint = models.CharField(
        max_length=512, verbose_name=_("API 端点"),
        null=True, blank=True,
        help_text=_("API 访问地址，如 https://cvm.tencentcloudapi.com"),
    )
    region = models.CharField(
        max_length=128, verbose_name=_("默认区域"),
        null=True, blank=True,
        help_text=_("默认区域标识，如 ap-guangzhou"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("启用状态"))

    class Meta:
        verbose_name = _("云平台实例")
        verbose_name_plural = verbose_name
        ordering = ['-created_time']

    def __str__(self) -> str:
        return f"{self.name} ({self.get_platform_type_display()})"


class Credential(DbAuditModel):
    """云平台认证凭据，支持多种认证方式。

    凭据类型：
    - access_key: 适用于公有云 ACCESS_KEY/SECRET_KEY 密钥对
    - password: 适用于用户名/密码登录（vCenter、美橙等），可配合 email 字段使用
    - api_token: 适用于 API Token 认证

    扩展机制：
    - email 字段：满足美橙等需要邮箱的场景
    - extra_data JSON 字段：存储任意额外的键值对，适配不同平台的个性化认证需求
    """

    class CredentialTypeChoices(models.TextChoices):
        """凭据类型枚举。"""

        ACCESS_KEY = "access_key", _("Access Key 密钥对")
        PASSWORD = "password", _("用户名/密码")
        API_TOKEN = "api_token", _("API Token")

    platform = models.ForeignKey(
        to=CloudPlatform,
        on_delete=models.CASCADE,
        related_name="credentials",
        verbose_name=_("所属平台"),
        help_text=_("该凭据归属的云平台实例"),
    )
    credential_type = models.CharField(
        max_length=32,
        choices=CredentialTypeChoices,
        verbose_name=_("凭据类型"),
    )
    credential_name = models.CharField(
        max_length=128, verbose_name=_("凭据名称"),
        help_text=_("自定义凭据标识，如：运维账号"),
    )

    # --- Access Key 类型字段 ---
    access_key = EncryptedTextField(
        verbose_name=_("Access Key ID"),
        null=True, blank=True, default="",
        help_text=_("云平台 Access Key ID（加密存储）"),
    )
    access_secret = EncryptedTextField(
        verbose_name=_("Secret Access Key"),
        null=True, blank=True, default="",
        help_text=_("云平台 Secret Access Key（加密存储）"),
    )

    # --- 用户名密码类型字段 ---
    username = models.CharField(
        max_length=128, verbose_name=_("用户名"),
        null=True, blank=True,
        help_text=_("登录用户名"),
    )
    password = EncryptedTextField(
        verbose_name=_("密码"),
        null=True, blank=True, default="",
        help_text=_("登录密码（加密存储）"),
    )
    email = models.EmailField(
        verbose_name=_("邮箱"),
        null=True, blank=True,
        help_text=_("关联邮箱（美橙等部分服务商认证需要）"),
    )

    # --- API Token 类型字段 ---
    api_token = EncryptedTextField(
        verbose_name=_("API Token"),
        null=True, blank=True, default="",
        help_text=_("API 访问令牌（加密存储）"),
    )
    token_expire_time = models.DateTimeField(
        verbose_name=_("Token 过期时间"),
        null=True, blank=True,
        help_text=_("Token 过期时间，为空表示永不过期"),
    )

    # --- 通用字段 ---
    extra_data = models.JSONField(
        verbose_name=_("扩展数据"),
        null=True, blank=True, default=dict,
        help_text=_("扩展 JSON 字段，存储不同平台的个性化认证键值对"),
    )
    remark = models.TextField(
        verbose_name=_("备注"),
        null=True, blank=True,
        help_text=_("凭据用途说明"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("启用状态"))

    class Meta:
        verbose_name = _("云平台凭据")
        verbose_name_plural = verbose_name
        ordering = ['platform', '-created_time']

    def __str__(self) -> str:
        return f"{self.platform.name} - {self.credential_name} ({self.get_credential_type_display()})"
