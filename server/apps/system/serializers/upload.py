"""上传文件序列化器。"""

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.core.serializers import BaseModelSerializer
from apps.common.fields.utils import get_file_absolute_uri
from apps.common.utils import get_logger
from apps.system.models import UploadFile

logger = get_logger(__name__)


class UploadFileSerializer(BaseModelSerializer):
    """上传文件序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UploadFile
        fields = ['pk', 'filename', 'filesize', 'mime_type', 'md5sum', 'file_url', 'access_url', 'is_tmp', 'is_upload']
        read_only_fields = ['pk', 'is_upload']
        table_fields = ['pk', 'filename', 'filesize', 'mime_type', 'access_url', 'is_tmp', 'is_upload', 'md5sum']
        extra_kwargs = {
            'filename': {'label': _('Filename'), 'help_text': _('Name of the uploaded file')},
            'filesize': {'label': _('Filesize'), 'help_text': _('Size of the uploaded file in bytes')},
            'mime_type': {'label': _('Mime type'), 'help_text': _('MIME type of the uploaded file')},
            'md5sum': {'label': _('File md5sum'), 'help_text': _('MD5 checksum of the uploaded file content')},
            'file_url': {'label': _('Internet URL'),
                         'help_text': _('Usually an address accessible to the outside Internet')},
            'is_tmp': {'label': _('Tmp file'),
                       'help_text': _('Temporary files are automatically cleared by scheduled tasks')},
            'is_upload': {'label': _('Upload file'), 'help_text': _('Whether the file was uploaded by a user')},
        }

    access_url = serializers.SerializerMethodField(label=_('Access URL'),
                                                   help_text=_('Accessible URL of the file'))

    @extend_schema_field(serializers.CharField)
    def get_access_url(self, obj: UploadFile) -> str:
        """获取文件的访问 URL。

        Args:
            obj: UploadFile 模型实例。

        Returns:
            文件的外部访问 URL。
        """
        return obj.file_url if obj.file_url else get_file_absolute_uri(obj.filepath, self.context.get('request', None))

    def create(self, validated_data: dict) -> UploadFile:
        """创建上传文件记录，确保外部 URL 不为空。

        Args:
            validated_data: 已验证的数据字典。

        Returns:
            创建的 UploadFile 实例。
        """
        if not validated_data.get('file_url'):
            raise ValidationError(_('Internet url cannot be null'))
        return super().create(validated_data)

    def update(self, instance: UploadFile, validated_data: dict) -> UploadFile:
        """更新上传文件记录，确保外部 URL 不为空。

        Args:
            instance: 待更新的 UploadFile 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 UploadFile 实例。
        """
        if not validated_data.get('file_url') and not instance.is_upload:
            raise ValidationError('Internet url cannot be null')
        return super().update(instance, validated_data)
