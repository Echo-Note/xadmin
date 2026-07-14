#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : message
# author : ly_13
# date : 9/15/2024
"""消息内容模型定义。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, AutoCleanFileMixin


class MessageContent(AutoCleanFileMixin, DbAuditModel):
    """消息内容模型，存储通知消息内容及关联的用户、部门、角色。"""

    class NoticeChoices(models.IntegerChoices):
        """通知类型枚举。"""

        SYSTEM = 0, _("System notification")
        NOTICE = 1, _("System announcement")
        USER = 2, _("User notification")
        DEPT = 3, _("Department notification")
        ROLE = 4, _("Role notification")

    class LevelChoices(models.TextChoices):
        """通知级别枚举。"""

        DEFAULT = 'info', _("Ordinary notices")
        PRIMARY = 'primary', _("General notices")
        SUCCESS = 'success', _("Success notices")
        DANGER = 'danger', _("Important notices")

    notice_user = models.ManyToManyField("system.UserInfo", through="MessageUserRead", blank=True,
                                         through_fields=('notice', 'owner'), verbose_name=_("The notified user"),
                                         help_text=_("Select the users who will receive this notification"))
    notice_dept = models.ManyToManyField("system.DeptInfo", blank=True,
                                         verbose_name=_("The notified department"),
                                         help_text=_("Select the departments whose members will receive this notification"))
    notice_role = models.ManyToManyField("system.UserRole", blank=True,
                                         verbose_name=_("The notified role"),
                                         help_text=_("Select the roles whose members will receive this notification"))
    level = models.CharField(verbose_name=_("Notice level"), choices=LevelChoices, default=LevelChoices.DEFAULT,
                             max_length=20, help_text=_("Priority level of the notification: info, primary, success, or danger"),
                             db_comment="通知级别（info/primary/success/danger）")
    notice_type = models.SmallIntegerField(verbose_name=_("Notice type"), choices=NoticeChoices,
                                           default=NoticeChoices.USER,
                                           help_text=_("Type of notification: system, announcement, user, department, or role"),
                                           db_comment="通知类型（0-系统 1-公告 2-用户 3-部门 4-角色）")
    title = models.CharField(verbose_name=_("Notice title"), max_length=255, help_text=_("Brief title summarizing the notification content"), db_comment="通知标题")
    message = models.TextField(verbose_name=_("Notice message"), blank=True, null=True, help_text=_("Detailed body content of the notification message"), db_comment="通知消息内容")
    extra_json = models.JSONField(verbose_name=_("Additional json data"), blank=True, null=True, help_text=_("Optional JSON payload for additional structured data attached to the notification"), db_comment="附加JSON数据")
    file = models.ManyToManyField("system.UploadFile", verbose_name=_("Uploaded attachments"), help_text=_("Files attached to this notification, such as documents or images"))
    publish = models.BooleanField(verbose_name=_("Publish"), default=True, help_text=_("Whether this notification is published and visible to recipients"), db_comment="是否发布")

    @classmethod
    def get_user_choices(cls):
        """返回与用户直接相关的通知类型列表。"""
        return [cls.NoticeChoices.USER, cls.NoticeChoices.SYSTEM]

    @classmethod
    def get_notice_choices(cls):
        """返回与公告、部门、角色相关的通知类型列表。"""
        return [cls.NoticeChoices.NOTICE, cls.NoticeChoices.DEPT, cls.NoticeChoices.ROLE]

    class Meta:
        """元数据配置。"""

        verbose_name = _("Message content")
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        db_table_comment = "消息内容表，存储通知消息内容及关联的用户、部门、角色"

    def __str__(self):
        """返回消息标题与类型显示名。"""
        return f"{self.title}-{self.get_notice_type_display()}"


class MessageUserRead(DbAuditModel):
    """用户消息已读记录模型。"""

    owner = models.ForeignKey("system.UserInfo", on_delete=models.CASCADE, verbose_name=_("User"), help_text=_("The user to whom this message read record belongs"), db_comment="消息所属用户")
    notice = models.ForeignKey(MessageContent, on_delete=models.CASCADE, verbose_name=_("Notice"), help_text=_("Reference to the message content this read record tracks"), db_comment="关联的消息内容")
    unread = models.BooleanField(verbose_name=_("Unread"), default=True, blank=False, db_index=True, help_text=_("Whether the message is still unread by the user; true means unread"), db_comment="是否未读")

    class Meta:
        """元数据配置。"""

        ordering = ('-created_time',)
        verbose_name = _("User read message")
        verbose_name_plural = verbose_name
        indexes = [models.Index(fields=['owner', 'unread'])]
        unique_together = ('owner', 'notice')
        db_table_comment = "用户消息已读记录表，记录用户对消息的已读状态"
