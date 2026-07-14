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
                                 format='png', help_text=_('User profile image, automatically resized to 512x512 pixels and stored in PNG format'), db_comment="用户头像")

    nickname = models.CharField(verbose_name=_('Nickname'), max_length=150, blank=True, help_text=_('The display name of the user, shown instead of username when available'), db_comment="用户昵称")
    gender = models.IntegerField(choices=GenderChoices, default=GenderChoices.UNKNOWN, verbose_name=_('Gender'), help_text=_('User gender: 0 for unknown, 1 for male, 2 for female'), db_comment="性别（0-未知 1-男 2-女）")
    phone = models.CharField(verbose_name=_('Phone'), max_length=16, default='', blank=True, db_index=True, help_text=_('User mobile phone number, used for contact and SMS notifications'), db_comment="手机号码")
    email = models.EmailField(verbose_name=_('Email'), default='', blank=True, db_index=True, help_text=_('User email address, used for notifications and password recovery'), db_comment="邮箱地址")

    roles = models.ManyToManyField(to='system.UserRole', verbose_name=_('Role permission'), blank=True, help_text=_('The role permissions assigned to this user, determining menu and API access'))
    rules = models.ManyToManyField(to='system.DataPermission', verbose_name=_('Data permission'), blank=True, help_text=_('The data permission rules assigned to this user for row-level data filtering'))
    dept = models.ForeignKey(to='system.DeptInfo', verbose_name=_('Department'), on_delete=models.PROTECT, blank=True,
                             null=True, related_query_name='dept_query',
                             help_text=_('The department this user belongs to, protected from deletion when referenced'),
                             db_comment="所属部门")

    class Meta:
        """用户元数据。"""

        verbose_name = _('Userinfo')
        verbose_name_plural = verbose_name
        ordering = ('-date_joined',)
        db_table_comment = "用户信息表，扩展Django AbstractUser"

    def __str__(self) -> str:
        """返回昵称和用户名的字符串表示。"""
        return f'{self.nickname}({self.username})'
