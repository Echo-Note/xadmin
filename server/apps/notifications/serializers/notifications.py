#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : notifications
# author : ly_13
# date : 9/13/2024
"""消息订阅序列化器定义。"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.common.core.fields import BasePrimaryKeyRelatedField
from apps.common.core.serializers import BaseModelSerializer
from apps.notifications.models import SystemMsgSubscription, UserMsgSubscription


class SystemMsgSubscriptionSerializer(BaseModelSerializer):
    """系统消息订阅序列化器。"""

    ignore_field_permission = True
    receive_backends = serializers.ListField(child=serializers.CharField(), label=_("Receive backends"),
                                             help_text=_("List of backend channels used to receive messages"))
    message_type_label = serializers.CharField(read_only=True, label=_("Message type label"),
                                               help_text=_("Human-readable label of the message type"))
    receivers = BasePrimaryKeyRelatedField(attrs=['pk', 'username', 'nickname'], read_only=True, source='users',
                                           label=_("User"), many=True, format='{nickname}({username})',
                                           help_text=_("Users who receive this system message subscription"))

    class Meta:
        """元数据配置。"""

        model = SystemMsgSubscription
        fields = ['message_type', 'message_type_label', 'users', 'receive_backends', 'receivers']
        read_only_fields = ['pk', 'message_type', 'message_type_label', 'receivers']
        extra_kwargs = {
            'message_type': {'label': _('Message type'),
                             'help_text': _('Unique identifier of the system message type')},
            'users': {'allow_empty': True, 'label': _('Users'),
                      'help_text': _('Users subscribed to this system message type')},
            'receive_backends': {'required': True, 'label': _('Receive backends'),
                                 'help_text': _('List of backend channels used to receive messages')},
        }


class SystemMsgSubscriptionByCategorySerializer(serializers.Serializer):
    """按分类分组的系统消息订阅序列化器。"""

    category = serializers.CharField(label=_('Category'), help_text=_('Identifier of the message category'))
    category_label = serializers.CharField(label=_('Category label'),
                                           help_text=_('Human-readable label of the message category'))
    children = SystemMsgSubscriptionSerializer(many=True, label=_('Children'),
                                               help_text=_('System message subscriptions under this category'))


class UserMsgSubscriptionSerializer(BaseModelSerializer):
    """用户消息订阅序列化器。"""

    ignore_field_permission = True
    receive_backends = serializers.ListField(child=serializers.CharField(), label=_("Receive backends"),
                                             help_text=_("List of backend channels used to receive messages"))
    message_type_label = serializers.CharField(read_only=True, label=_("Message Type"),
                                               help_text=_("Human-readable label of the message type"))
    receivers = BasePrimaryKeyRelatedField(attrs=['pk', 'username', 'nickname'], read_only=True, label=_("User"),
                                           source='user', format='{nickname}({username})',
                                           help_text=_("User who owns this message subscription"))

    class Meta:
        """元数据配置。"""

        model = UserMsgSubscription
        fields = ['message_type', 'message_type_label', 'user', 'receive_backends', 'receivers']
        read_only_fields = ['pk', 'message_type', 'message_type_label', 'receivers']
        extra_kwargs = {
            'message_type': {'label': _('Message type'),
                             'help_text': _('Identifier of the message type the user subscribes to')},
            'user': {'read_only': True, 'label': _('User'), 'help_text': _('The user who owns this subscription')},
            'receive_backends': {'required': True, 'label': _('Receive backends'),
                                 'help_text': _('List of backend channels used to receive messages')},
        }


class UserMsgSubscriptionByCategorySerializer(serializers.Serializer):
    """按分类分组的用户消息订阅序列化器。"""

    category = serializers.CharField(label=_('Category'), help_text=_('Identifier of the message category'))
    category_label = serializers.CharField(label=_('Category label'),
                                           help_text=_('Human-readable label of the message category'))
    children = UserMsgSubscriptionSerializer(many=True, label=_('Children'),
                                             help_text=_('User message subscriptions under this category'))
