"""用户模型。"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from pilkit.processors import ResizeToFill

from apps.common.core.models import upload_directory_path, DbAuditModel, AutoCleanFileMixin
from apps.common.fields.image import ProcessedImageField
from apps.system.models import ModeTypeAbstract


class UserInfo(AutoCleanFileMixin, DbAuditModel, AbstractUser, ModeTypeAbstract):
    """用户信息模型，扩展 Django AbstractUser，添加头像、角色、部门等字段。"""

    class GenderChoices(models.IntegerChoices):
        """性别选择。"""

        UNKNOWN = 0, _('Unknown')
        MALE = 1, _('Male')
        FEMALE = 2, _('Female')

    avatar = ProcessedImageField(verbose_name=_('Avatar'), null=True, blank=True,
                                 upload_to=upload_directory_path,
                                 processors=[ResizeToFill(512, 512)],  # 默认存储像素大小
                                 scales=[1, 2, 3, 4],  # 缩略图可缩小倍数，
                                 format='png')

    nickname = models.CharField(verbose_name=_('Nickname'), max_length=150, blank=True)
    gender = models.IntegerField(choices=GenderChoices, default=GenderChoices.UNKNOWN, verbose_name=_('Gender'))
    phone = models.CharField(verbose_name=_('Phone'), max_length=16, default='', blank=True, db_index=True)
    email = models.EmailField(verbose_name=_('Email'), default='', blank=True, db_index=True)

    roles = models.ManyToManyField(to='system.UserRole', verbose_name=_('Role permission'), blank=True)
    rules = models.ManyToManyField(to='system.DataPermission', verbose_name=_('Data permission'), blank=True)
    dept = models.ForeignKey(to='system.DeptInfo', verbose_name=_('Department'), on_delete=models.PROTECT, blank=True,
                             null=True, related_query_name='dept_query')

    class Meta:
        """用户元数据。"""

        verbose_name = _('Userinfo')
        verbose_name_plural = verbose_name
        ordering = ('-date_joined',)

    def __str__(self) -> str:
        """返回昵称和用户名的字符串表示。"""
        return f'{self.nickname}({self.username})'
