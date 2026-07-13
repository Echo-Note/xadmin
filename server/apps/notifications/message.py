"""站内信消息工具类，提供发送通知消息的封装方法。"""

import json
from typing import List, Dict

from django.db import transaction
from rest_framework.utils import encoders

from apps.common.core.config import UserConfig
from apps.common.utils import get_logger
from apps.message.utils import push_message, get_online_users
from apps.notifications.serializers.message import NoticeMessageSerializer
from apps.system.models import UserInfo

logger = get_logger(__name__)

from django.db.models import QuerySet

from apps.notifications.models import MessageContent

SYSTEM = MessageContent.NoticeChoices.SYSTEM


class SiteMessageUtil:
    """站内信消息工具类，封装消息创建与推送逻辑。"""

    @classmethod
    def send_msg(cls, subject: str, message: str, user_ids: list = None,
                 level: str = MessageContent.LevelChoices.DEFAULT,
                 notice_type: int = MessageContent.NoticeChoices.SYSTEM) -> None:
        """发送站内信消息。

        Args:
            subject: 消息主题。
            message: 消息正文。
            user_ids: 接收用户 ID 列表。
            level: 消息级别。
            notice_type: 通知类型。
        """
        if not user_ids:
            raise ValueError('No recipient is specified')

        cls.base_notify(user_ids, subject, message, notice_type, level)

    @classmethod
    def push_notice_messages(cls, notify_obj: MessageContent, pks: list):
        """向在线用户推送通知消息。

        Args:
            notify_obj: 通知对象。
            pks: 用户主键列表。

        Returns:
            通知对象。
        """
        notice_message = NoticeMessageSerializer(
            fields=['pk', 'level', 'title', 'notice_type', 'message'],
            instance=notify_obj, ignore_field_permission=True).data
        notice_message['message_type'] = 'notify_message'
        for pk in set(pks) & set(get_online_users()):
            if UserConfig(pk).PUSH_MESSAGE_NOTICE:
                push_message(pk, json.loads(json.dumps(notice_message, cls=encoders.JSONEncoder, ensure_ascii=False)))
        return notify_obj

    @classmethod
    def base_notify(cls, users: List | QuerySet, title: str, message: str, notice_type: int,
                    level: MessageContent.LevelChoices, extra_json: Dict = None) -> MessageContent:
        """创建通知消息并推送给在线用户。

        Args:
            users: 接收用户列表或查询集。
            title: 消息标题。
            message: 消息正文。
            notice_type: 通知类型。
            level: 消息级别。
            extra_json: 额外 JSON 数据。

        Returns:
            创建的通知对象。
        """
        if isinstance(users, (QuerySet, list)):
            recipients = users
        else:
            recipients = [users]
        with transaction.atomic():
            notify_obj = MessageContent.objects.create(
                title=title,
                publish=True,
                message=message,
                level=level,
                notice_type=notice_type,
                extra_json=extra_json
            )
            notify_obj.notice_user.set(recipients)
        cls.push_notice_messages(notify_obj, [user.pk for user in recipients] if isinstance(recipients[0],
                                                                                            UserInfo) else recipients)
        return notify_obj

    @classmethod
    def notify_success(cls, users: List | QuerySet, title: str, message: str, notice_type: int = SYSTEM,
                       extra_json: Dict = None) -> MessageContent:
        """发送成功级别的通知消息。"""
        return cls.base_notify(users, title, message, notice_type, MessageContent.LevelChoices.SUCCESS, extra_json)

    @classmethod
    def notify_info(cls, users: List | QuerySet, title: str, message: str, notice_type: int = SYSTEM,
                    extra_json: Dict = None) -> MessageContent:
        """发送普通级别的通知消息。"""
        return cls.base_notify(users, title, message, notice_type, MessageContent.LevelChoices.PRIMARY, extra_json)

    @classmethod
    def notify_error(cls, users: List | QuerySet, title: str, message: str, notice_type: int = SYSTEM,
                     extra_json: Dict = None) -> MessageContent:
        """发送重要级别的通知消息。"""
        return cls.base_notify(users, title, message, notice_type, MessageContent.LevelChoices.DANGER, extra_json)
