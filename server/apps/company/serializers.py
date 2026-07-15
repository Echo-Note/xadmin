"""公司主体管理的序列化器。"""

from django.utils.translation import gettext_lazy as _

from apps.common.core.serializers import BaseModelSerializer
from apps.company import models


class CompanySerializer(BaseModelSerializer):
    """公司主体序列化器。"""

    class Meta:
        """序列化器元数据配置。"""

        model = models.Company
        fields = [
            'pk',
            'name',
            'short_name',
            'is_active',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'name',
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
            'short_name': {
                'label': _('简称'),
                'help_text': _('公司简称，方便列表展示'),
            },
            'is_active': {
                'label': _('启用状态'),
                'help_text': _('公司是否启用，启用后可在业务中使用'),
            },
            'description': {
                'label': _('Description'),
                'help_text': _('描述信息'),
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
