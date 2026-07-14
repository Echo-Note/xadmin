#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : notification
# author : ly_13
# date : 9/13/2024
"""消息订阅模型定义。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel


class UserMsgSubscription(DbAuditModel):
    """用户消息订阅模型，记录用户对各类消息的接收后端偏好。"""

    message_type = models.CharField(max_length=128, verbose_name=_('message type'), help_text=_("Identifier of the message type the user subscribes to"), db_comment="消息类型")
    user = models.ForeignKey('system.UserInfo', related_name='user_msg_subscription', on_delete=models.CASCADE,
                             verbose_name=_('User'), help_text=_("The user who owns this subscription preference"),
                             db_comment="订阅用户")
    receive_backends = models.JSONField(default=list, verbose_name=_('receive backend'), help_text=_("List of backend channels for message delivery, e.g. ['email', 'sms', 'websocket']"), db_comment="消息接收后端列表")

    class Meta:
        """元数据配置。"""

        verbose_name = _('User message subscription')
        unique_together = (('user', 'message_type'),)
        db_table_comment = "用户消息订阅表，记录用户对各类消息的接收后端偏好"

    def __str__(self):
        """返回用户订阅描述。"""
        return _('{} subscription').format(self.user)


class SystemMsgSubscription(DbAuditModel):
    """系统消息订阅模型，记录系统级消息类型及接收用户集合。"""

    message_type = models.CharField(max_length=128, unique=True, verbose_name=_('message type'), help_text=_("Unique system-level message type identifier"), db_comment="系统消息类型")
    users = models.ManyToManyField('system.UserInfo', related_name='system_msg_subscriptions', verbose_name=_("User"), help_text=_("Users who will receive this system message type through the configured backends"))
    receive_backends = models.JSONField(default=list, verbose_name=_('receive backend'), help_text=_("List of backend channels for delivering this system message type"), db_comment="消息接收后端列表")

    class Meta:
        """元数据配置。"""

        verbose_name = _('System message subscription')
        db_table_comment = "系统消息订阅表，记录系统级消息类型及接收用户集合"

    def __str__(self):
        """返回消息类型与接收后端的描述。"""
        return f'{self.message_type} -- {self.receive_backends}'
