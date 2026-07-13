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

    message_type = models.CharField(max_length=128, verbose_name=_('message type'))
    user = models.ForeignKey('system.UserInfo', related_name='user_msg_subscription', on_delete=models.CASCADE,
                             verbose_name=_('User'))
    receive_backends = models.JSONField(default=list, verbose_name=_('receive backend'))

    class Meta:
        """元数据配置。"""

        verbose_name = _('User message subscription')
        unique_together = (('user', 'message_type'),)

    def __str__(self):
        """返回用户订阅描述。"""
        return _('{} subscription').format(self.user)


class SystemMsgSubscription(DbAuditModel):
    """系统消息订阅模型，记录系统级消息类型及接收用户集合。"""

    message_type = models.CharField(max_length=128, unique=True, verbose_name=_('message type'))
    users = models.ManyToManyField('system.UserInfo', related_name='system_msg_subscriptions', verbose_name=_("User"))
    receive_backends = models.JSONField(default=list, verbose_name=_('receive backend'))

    class Meta:
        """元数据配置。"""

        verbose_name = _('System message subscription')

    def __str__(self):
        """返回消息类型与接收后端的描述。"""
        return f'{self.message_type} -- {self.receive_backends}'
