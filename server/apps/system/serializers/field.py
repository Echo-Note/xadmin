"""模型字段标签序列化器。"""

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import ModelLabelField

logger = get_logger(__name__)


class ModelLabelFieldSerializer(BaseModelSerializer):
    """模型字段标签序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = ModelLabelField
        fields = ['pk', 'name', 'label', 'parent', 'field_type', 'created_time', 'updated_time']
        read_only_fields = [x.name for x in ModelLabelField._meta.fields]
        extra_kwargs = {'parent': {'attrs': ['pk', 'name', 'label'], 'read_only': True, 'format': '{label}({pk})'}}


class ModelLabelFieldImportSerializer(BaseModelSerializer):
    """模型字段标签导入序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = ModelLabelField
        fields = ['pk', 'name', 'label', 'parent', 'field_type', 'created_time', 'updated_time']
