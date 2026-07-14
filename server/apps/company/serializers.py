"""公司主体管理的序列化器。"""

from apps.common.core.serializers import BaseModelSerializer
from apps.company import models


class CompanySerializer(BaseModelSerializer):
    """公司主体序列化器。"""

    class Meta:
        model = models.Company
        fields = [
            'pk', 'name', 'short_name', 'is_active',
            'description', 'created_time', 'updated_time',
        ]
        table_fields = [
            'pk', 'name', 'short_name', 'is_active', 'created_time',
        ]
        extra_kwargs = {
            'pk': {'read_only': True},
        }
