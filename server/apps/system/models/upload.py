"""上传文件模型。"""

import hashlib

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import upload_directory_path, DbAuditModel, AutoCleanFileMixin


class UploadFile(AutoCleanFileMixin, DbAuditModel):
    """上传文件模型，存储文件路径、MD5、大小等信息。"""

    filepath = models.FileField(verbose_name=_('Filepath'), null=True, blank=True, upload_to=upload_directory_path)
    file_url = models.URLField(verbose_name=_('Internet URL'), max_length=255, blank=True, null=True,
                               help_text=_('Usually an address accessible to the outside Internet'))
    filename = models.CharField(verbose_name=_('Filename'), max_length=255)
    filesize = models.IntegerField(verbose_name=_('Filesize'))
    mime_type = models.CharField(max_length=255, verbose_name=_('Mime type'))
    md5sum = models.CharField(max_length=36, verbose_name=_('File md5sum'))
    is_tmp = models.BooleanField(verbose_name=_('Tmp file'), default=False,
                                 help_text=_('Temporary files are automatically cleared by scheduled tasks'))
    is_upload = models.BooleanField(verbose_name=_('Upload file'), default=False)

    def save(self, *args, **kwargs) -> None:
        """保存前截断文件名并计算文件 MD5 值。

        Args:
            *args: 传递给父类 save 的位置参数。
            **kwargs: 传递给父类 save 的关键字参数。
        """
        self.filename = self.filename[:255]
        if not self.md5sum and not self.file_url:
            md5 = hashlib.md5()
            for chunk in self.filepath.chunks():
                md5.update(chunk)
            if not self.filesize:
                self.filesize = self.filepath.size
            self.md5sum = md5.hexdigest()
        super().save(*args, **kwargs)

    class Meta:
        """上传文件元数据。"""

        verbose_name = _('Upload file')
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        """返回文件名的字符串表示。"""
        return f'{self.filename}'
