"""模型字段标签序列化器。"""

from django.utils.translation import gettext_lazy as _

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
        extra_kwargs = {
            'parent': {'attrs': ['pk', 'name', 'label'], 'read_only': True, 'format': '{label}({pk})',
                       'label': _('Parent node'), 'help_text': _('Parent node of the model label field')},
            'name': {'label': _('Model/Field name'), 'help_text': _('Identifier name of the model or field')},
            'label': {'label': _('Model/Field label'), 'help_text': _('Display label of the model or field')},
            'field_type': {'label': _('Field type'),
                           'help_text': _('Field type: 0-Role permission, 1-Data permission')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
            'updated_time': {'label': _('Updated time'), 'help_text': _('Time when this record was last updated')},
        }


class ModelLabelFieldImportSerializer(BaseModelSerializer):
    """模型字段标签导入序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = ModelLabelField
        fields = ['pk', 'name', 'label', 'parent', 'field_type', 'created_time', 'updated_time']
        extra_kwargs = {
            'name': {'label': _('Model/Field name'), 'help_text': _('Identifier name of the model or field')},
            'label': {'label': _('Model/Field label'), 'help_text': _('Display label of the model or field')},
            'parent': {'label': _('Parent node'), 'help_text': _('Parent node of the model label field')},
            'field_type': {'label': _('Field type'),
                           'help_text': _('Field type: 0-Role permission, 1-Data permission')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when this record was created')},
            'updated_time': {'label': _('Updated time'), 'help_text': _('Time when this record was last updated')},
        }
