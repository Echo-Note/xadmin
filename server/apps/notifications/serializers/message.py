#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : message
# author : ly_13
# date : 9/15/2024
"""消息内容序列化器定义。"""

import os.path

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.common.core.filter import get_filter_queryset
from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.notifications.models import MessageUserRead, MessageContent
from apps.system.models import UploadFile, UserInfo

logger = get_logger(__name__)


class NoticeMessageSerializer(BaseModelSerializer):
    """通知消息内容序列化器。"""

    class Meta:
        """元数据配置。"""

        model = MessageContent
        fields = ['pk', 'title', 'level', "publish", 'notice_type', "notice_user", 'notice_dept', 'notice_role',
                  'message', "created_time", "user_count", "read_user_count", 'extra_json', "files"]

        table_fields = ['pk', 'title', 'notice_type', "read_user_count", "publish", "created_time"]
        extra_kwargs = {
            'extra_json': {'read_only': True},
            'notice_user': {'attrs': ['pk', 'username'], 'many': True, 'format': '{username}', 'read_only': False,
                            'input_type': 'api-search-user', 'queryset': UserInfo.objects},
            'notice_dept': {'attrs': ['pk', 'name'], 'many': True, 'format': '{name}', 'input_type': 'api-search-dept'},
            'notice_role': {'attrs': ['pk', 'name'], 'many': True, 'format': '{name}', 'input_type': 'api-search-role'},
        }

    files = serializers.JSONField(write_only=True, label=_("Uploaded attachments"))
    user_count = serializers.SerializerMethodField(read_only=True, label=_("User count"))
    read_user_count = serializers.SerializerMethodField(read_only=True, label=_("Read user count"))

    @extend_schema_field(serializers.IntegerField)
    def get_read_user_count(self, obj: MessageContent) -> int:
        """根据通知类型返回已读用户数。"""
        if obj.notice_type in MessageContent.get_user_choices():
            return MessageUserRead.objects.filter(notice=obj, unread=False,
                                                  owner_id__in=obj.notice_user.all()).count()

        elif obj.notice_type in MessageContent.get_notice_choices():
            return obj.notice_user.count()

        return 0

    @extend_schema_field(serializers.IntegerField)
    def get_user_count(self, obj: MessageContent) -> int:
        """根据通知类型返回目标用户总数。"""
        if obj.notice_type == MessageContent.NoticeChoices.DEPT:
            return UserInfo.objects.filter(dept__in=obj.notice_dept.all()).count()
        if obj.notice_type == MessageContent.NoticeChoices.ROLE:
            return UserInfo.objects.filter(roles__in=obj.notice_role.all()).count()
        return obj.notice_user.count()

    def validate_notice_type(self, val: int) -> int:
        """校验通知类型，系统公告不允许通过 POST 创建。"""
        if MessageContent.NoticeChoices.NOTICE == val and self.request.method == 'POST':
            raise ValidationError(_("Parameter error. System announcement cannot be created"))
        return val

    def validate(self, attrs: dict) -> dict:
        """校验通知对象与附件信息。"""
        notice_type = attrs.get('notice_type')

        if notice_type == MessageContent.NoticeChoices.ROLE:
            attrs.pop('notice_dept', None)
            attrs.pop('notice_user', None)
            if not attrs.get('notice_role'):
                raise ValidationError(_("The notice role cannot be null"))

        if notice_type == MessageContent.NoticeChoices.DEPT:
            attrs.pop('notice_user', None)
            attrs.pop('notice_role', None)
            if not attrs.get('notice_dept'):
                raise ValidationError(_("The notice department cannot be null"))

        if notice_type == MessageContent.NoticeChoices.USER:
            attrs.pop('notice_role', None)
            attrs.pop('notice_dept', None)
            if not attrs.get('notice_user'):
                raise ValidationError(_("The notice user cannot be null"))

        files = attrs.get('files')
        if files is not None:
            del attrs['files']
            queryset = UploadFile.objects.filter(
                filepath__in=[file.split(os.path.join('/', settings.MEDIA_URL))[-1] for file in files])
            attrs['file'] = get_filter_queryset(queryset, self.request.user).all()
        return attrs


    def update(self, instance: MessageContent, validated_data: dict) -> MessageContent:
        """更新消息内容，系统通知不允许修改。"""
        validated_data.pop('notice_type', None)  # 不能修改消息类型
        if instance.notice_type == MessageContent.NoticeChoices.SYSTEM:  # 系统通知不允许修改
            raise ValidationError(_("The system notice cannot be update"))
        return super().update(instance, validated_data)


class AnnouncementSerializer(NoticeMessageSerializer):
    """系统公告序列化器。"""

    def validate_notice_type(self, val: int) -> int:
        """校验通知类型必须为系统公告。"""
        if MessageContent.NoticeChoices.NOTICE == val:
            return val
        raise ValidationError(_("Parameter error"))


class NoticeUserReadMessageSerializer(BaseModelSerializer):
    """用户已读消息序列化器。"""

    class Meta:
        """元数据配置。"""

        model = MessageUserRead
        fields = ['pk', 'notice_info', 'notice_type', 'owner', "unread", "updated_time"]
        read_only_fields = [x.name for x in MessageUserRead._meta.fields]
        extra_kwargs = {
            'owner': {'attrs': ['pk', 'username'], 'read_only': True}
        }

    notice_type = serializers.CharField(source='notice.get_notice_type_display', read_only=True, label=_("Notice type"))

    notice_info = NoticeMessageSerializer(fields=['pk', 'level', 'title', 'notice_type', 'message', 'publish'],
                                          read_only=True, source='notice', label=_("Notice message"))


class UserNoticeSerializer(BaseModelSerializer):
    """用户消息中心序列化器。"""

    ignore_field_permission = True

    class Meta:
        """元数据配置。"""

        model = MessageContent
        fields = ['pk', 'level', 'title', 'message', "created_time", 'unread', 'notice_type']
        table_fields = ['pk', 'title', 'unread', 'notice_type', "created_time"]
        read_only_fields = ['pk', 'notice_user', 'notice_type']

    unread = serializers.SerializerMethodField(label=_("Unread"))

    @extend_schema_field(serializers.BooleanField)
    def get_unread(self, obj: MessageContent) -> bool:
        """根据通知类型判断当前用户是否未读。"""
        queryset = MessageUserRead.objects.filter(notice=obj, owner=self.context.get('request').user)
        if obj.notice_type in MessageContent.get_user_choices():
            return bool(queryset.filter(unread=True).count())
        elif obj.notice_type in MessageContent.get_notice_choices():
            return not bool(queryset.count())
        return True
