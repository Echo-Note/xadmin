"""公司主体管理的模型定义。

Company 作为独立 app，可被 cloud_platform 等其他应用通过外键引用。
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel, upload_directory_path
from apps.common.fields.encrypted import EncryptedTextField
from apps.company.choices import CompanyTypeChoices


class Company(DbAuditModel, DbUuidModel):
    """公司主体，用于标识业务归属的企业/组织。

    其他应用（如云平台管理、项目管理等）可通过 ForeignKey 关联到此模型，
    实现统一的公司主体管理。

    字段分组：
    - 基本信息：名称、统一社会信用代码、类型、法定代表人、成立日期、
      住所、注册资本、经营范围、简称、启用状态
    - 证照文件：营业执照、法人身份证正反面
    - 联系方式：法人联系方式（加密存储）
    """

    # ---------- 基本信息 ----------
    name = models.CharField(
        max_length=128,
        verbose_name=_('公司名称'),
        unique=True,
        db_comment='公司全称，唯一标识一个公司主体',
        help_text=_('公司全称，用于唯一标识一个公司主体'),
    )
    unified_social_credit_code = models.CharField(
        max_length=18,
        verbose_name=_('统一社会信用代码'),
        unique=True,
        null=True,
        blank=True,
        db_comment='统一社会信用代码，18位',
        help_text=_('18位统一社会信用代码，营业执照上登记的唯一代码'),
    )
    company_type = models.CharField(
        max_length=32,
        choices=CompanyTypeChoices,
        default=CompanyTypeChoices.LIMITED_LIABILITY,
        verbose_name=_('公司类型'),
        db_comment='公司类型枚举值',
        help_text=_('公司类型：有限责任公司/股份有限公司/个人独资企业/合伙企业/个体工商户/其他'),
    )
    legal_representative = models.CharField(
        max_length=64,
        verbose_name=_('法定代表人'),
        null=True,
        blank=True,
        db_comment='法定代表人姓名',
        help_text=_('公司法定代表人姓名'),
    )
    establishment_date = models.DateField(
        verbose_name=_('成立日期'),
        null=True,
        blank=True,
        db_comment='公司成立日期',
        help_text=_('营业执照上登记的成立日期'),
    )
    registered_address = models.CharField(
        max_length=256,
        verbose_name=_('住所'),
        null=True,
        blank=True,
        db_comment='公司注册地址（住所）',
        help_text=_('营业执照上登记的住所/注册地址'),
    )
    registered_capital = models.CharField(
        max_length=64,
        verbose_name=_('注册资本'),
        null=True,
        blank=True,
        db_comment='注册资本及币种',
        help_text=_('注册资本，含币种信息，如"100万元人民币"'),
    )
    business_scope = models.TextField(
        verbose_name=_('经营范围'),
        null=True,
        blank=True,
        db_comment='经营范围描述',
        help_text=_('营业执照上登记的经营范围'),
    )
    short_name = models.CharField(
        max_length=64,
        verbose_name=_('简称'),
        null=True,
        blank=True,
        db_comment='公司简称，方便列表展示',
        help_text=_('公司简称，方便列表展示'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('启用状态'),
        db_comment='公司是否启用',
        help_text=_('公司是否启用，启用后可在业务中使用'),
    )

    # ---------- 证照文件 ----------
    business_license = models.FileField(
        verbose_name=_('营业执照'),
        upload_to=upload_directory_path,
        null=True,
        blank=True,
        db_comment='营业执照扫描件或照片',
        help_text=_('公司营业执照扫描件或照片'),
    )
    legal_representative_id_front = models.FileField(
        verbose_name=_('法人身份证正面'),
        upload_to=upload_directory_path,
        null=True,
        blank=True,
        db_comment='法定代表人身份证正面照片',
        help_text=_('法定代表人身份证正面照片'),
    )
    legal_representative_id_back = models.FileField(
        verbose_name=_('法人身份证反面'),
        upload_to=upload_directory_path,
        null=True,
        blank=True,
        db_comment='法定代表人身份证反面照片',
        help_text=_('法定代表人身份证反面照片'),
    )

    # ---------- 联系方式 ----------
    legal_representative_contact = EncryptedTextField(
        verbose_name=_('法人联系方式'),
        null=True,
        blank=True,
        default='',
        db_comment='法定代表人联系方式（加密存储）',
        help_text=_('法定代表人联系电话或其他联系方式（加密存储）'),
    )

    class Meta:
        """元数据配置。"""

        verbose_name = _('公司主体')
        verbose_name_plural = verbose_name
        ordering = ['name']
        db_table_comment = _('公司主体表，记录企业/组织的工商登记信息、证照文件及联系方式')

    def __str__(self) -> str:
        """返回公司简称或全称。"""
        return self.short_name or self.name
