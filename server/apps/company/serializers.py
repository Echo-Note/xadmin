"""公司主体管理的序列化器。"""

from django.utils.translation import gettext_lazy as _

from apps.common.core.serializers import BaseModelSerializer, TabsColumn
from apps.company import models


class CompanySerializer(BaseModelSerializer):
    """公司主体序列化器，包含工商登记信息、证照文件及法人联系方式。"""

    class Meta:
        """序列化器元数据配置。"""

        model = models.Company
        tabs = [
            TabsColumn(
                '基本信息',
                [
                    'name',
                    'unified_social_credit_code',
                    'company_type',
                    'legal_representative',
                    'establishment_date',
                    'registered_address',
                    'registered_capital',
                    'business_scope',
                    'short_name',
                    'is_active',
                    'description',
                ],
            ),
            TabsColumn(
                '证照文件',
                [
                    'business_license',
                    'legal_representative_id_front',
                    'legal_representative_id_back',
                ],
            ),
            TabsColumn(
                '联系方式',
                [
                    'legal_representative_contact',
                ],
            ),
        ]
        fields = [
            'pk',
            'name',
            'unified_social_credit_code',
            'company_type',
            'legal_representative',
            'establishment_date',
            'registered_address',
            'registered_capital',
            'business_scope',
            'short_name',
            'is_active',
            'business_license',
            'legal_representative_id_front',
            'legal_representative_id_back',
            'legal_representative_contact',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'name',
            'unified_social_credit_code',
            'company_type',
            'legal_representative',
            'establishment_date',
            'short_name',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': _('ID'),
                'help_text': _('主键唯一标识'),
            },
            'name': {
                'label': _('公司名称'),
                'help_text': _('公司全称，用于唯一标识一个公司主体'),
            },
            'unified_social_credit_code': {
                'label': _('统一社会信用代码'),
                'help_text': _('18位统一社会信用代码，营业执照上登记的唯一代码'),
            },
            'company_type': {
                'label': _('公司类型'),
                'help_text': _('公司类型：有限责任公司/股份有限公司/个人独资企业/合伙企业/个体工商户/其他'),
            },
            'legal_representative': {
                'label': _('法定代表人'),
                'help_text': _('公司法定代表人姓名'),
            },
            'establishment_date': {
                'label': _('成立日期'),
                'help_text': _('营业执照上登记的成立日期'),
            },
            'registered_address': {
                'label': _('住所'),
                'help_text': _('营业执照上登记的住所/注册地址'),
            },
            'registered_capital': {
                'label': _('注册资本'),
                'help_text': _('注册资本，含币种信息，如"100万元人民币"'),
            },
            'business_scope': {
                'label': _('经营范围'),
                'help_text': _('营业执照上登记的经营范围'),
            },
            'short_name': {
                'label': _('简称'),
                'help_text': _('公司简称，方便列表展示'),
            },
            'is_active': {
                'label': _('启用状态'),
                'help_text': _('公司是否启用，启用后可在业务中使用'),
            },
            'business_license': {
                'label': _('营业执照'),
                'help_text': _('公司营业执照扫描件或照片'),
            },
            'legal_representative_id_front': {
                'label': _('法人身份证正面'),
                'help_text': _('法定代表人身份证正面照片'),
            },
            'legal_representative_id_back': {
                'label': _('法人身份证反面'),
                'help_text': _('法定代表人身份证反面照片'),
            },
            'legal_representative_contact': {
                'label': _('法人联系方式'),
                'help_text': _('法定代表人联系电话或其他联系方式（加密存储）'),
            },
            'description': {
                'label': _('Description'),
                'help_text': _('备注说明'),
            },
            'created_time': {
                'read_only': True,
                'label': _('Created time'),
                'help_text': _('创建时间'),
            },
            'updated_time': {
                'read_only': True,
                'label': _('Updated time'),
                'help_text': _('更新时间'),
            },
        }
