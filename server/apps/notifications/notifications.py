#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : notifications
# author : ly_13
# date : 9/13/2024
"""消息通知核心模块，封装消息模板与统一发送接口。"""

import textwrap
import traceback
from functools import cached_property
from typing import List

from celery import shared_task
from django.utils.translation import gettext_lazy as _
from html2text import HTML2Text

from apps.common.utils import get_logger
from apps.common.utils.timezone import local_now
from apps.notifications.backends import BACKEND
from apps.notifications.models import SystemMsgSubscription, UserMsgSubscription
from apps.system.models import UserInfo

logger = get_logger(__name__)
system_msgs: list = []
user_msgs: list = []


class MessageType(type):
    """消息元类，在类创建时自动注册具有完整属性的消息类型。"""

    def __new__(cls, name: str, bases: tuple, attrs: dict):
        """创建消息类并注册到全局消息列表。"""
        clz = type.__new__(cls, name, bases, attrs)

        if 'message_type_label' in attrs \
                and 'category' in attrs \
                and 'category_label' in attrs:
            message_type = clz.get_message_type()

            msg = {
                'message_type': message_type,
                'message_type_label': attrs['message_type_label'],
                'category': attrs['category'],
                'category_label': attrs['category_label'],
            }
            if issubclass(clz, SystemMessage):
                system_msgs.append(msg)
            elif issubclass(clz, UserMessage):
                user_msgs.append(msg)

        return clz


@shared_task(verbose_name=_('Publish the station message'))
def publish_task(receive_user_ids: list, backends_msg_mapper: dict) -> None:
    """异步发布站内消息的 Celery 任务。"""
    Message.send_msg(receive_user_ids, backends_msg_mapper)


class Message(metaclass=MessageType):
    """
    消息基类，封装不同消息的模板，提供统一的发送消息接口。

    Attributes:
        publish: 发布消息的方法，与消息订阅表结构相关。
        send_msg: 发送消息的静态方法。
    """

    message_type_label: str
    category: str
    category_label: str
    text_msg_ignore_links = True

    @classmethod
    def get_message_type(cls) -> str:
        """返回当前消息类型的名称。"""
        return cls.__name__

    def publish_async(self) -> None:
        """异步发布消息。"""
        self.publish(is_async=True)

    @classmethod
    def gen_test_msg(cls):
        """生成测试消息，子类必须实现。"""
        raise NotImplementedError

    def publish(self, is_async: bool = False) -> None:
        """发布消息，子类必须实现。"""
        raise NotImplementedError

    def get_backend_msg_mapper(self, backends: list) -> dict:
        """构建后端到消息内容的映射。

        Args:
            backends: 后端列表。

        Returns:
            后端到消息内容的映射字典。
        """
        backends = set(backends)
        backends.add(BACKEND.SITE_MSG)  # 站内信必须发
        backends_msg_mapper = {}
        for backend in backends:
            backend = BACKEND(backend)
            if not backend.is_enable:
                continue
            get_msg_method = getattr(self, f'get_{backend}_msg', self.get_common_msg)
            msg = get_msg_method()
            backends_msg_mapper[backend] = msg
        return backends_msg_mapper

    @staticmethod
    def send_msg(receive_user_ids: list, backends_msg_mapper: dict) -> None:
        """通过各后端向指定用户发送消息。

        Args:
            receive_user_ids: 接收用户 ID 列表。
            backends_msg_mapper: 后端到消息内容的映射。
        """
        for backend, msg in backends_msg_mapper.items():
            try:
                backend = BACKEND(backend)
                client = backend.client()
                users = UserInfo.objects.filter(id__in=receive_user_ids).all()
                client.send_msg(users, **msg)
            except NotImplementedError:
                continue
            except:
                traceback.print_exc()

    @classmethod
    def send_test_msg(cls) -> None:
        """向超级用户发送测试消息。"""
        msg = cls.gen_test_msg()
        if not msg:
            return

        from apps.system.models import UserInfo
        users = UserInfo.objects.filter(is_superuser=True)
        backends = []
        msg.send_msg(users, backends)

    @staticmethod
    def get_common_msg() -> dict:
        """返回通用消息模板。"""
        return {'subject': '', 'message': ''}

    def get_html_msg(self) -> dict:
        """返回 HTML 格式消息，子类可覆写。"""
        return self.get_common_msg()

    @staticmethod
    def html_to_markdown(html_msg: dict) -> dict:
        """将 HTML 消息转换为 Markdown 格式。

        Args:
            html_msg: 包含 HTML 内容的消息字典。

        Returns:
            转换后的消息字典。
        """
        h = HTML2Text()
        h.body_width = 0
        content = html_msg['message']
        html_msg['message'] = h.handle(content)
        return html_msg

    def get_markdown_msg(self) -> dict:
        """返回 Markdown 格式消息。"""
        return self.html_to_markdown(self.get_html_msg())

    def get_text_msg(self) -> dict:
        """返回纯文本格式消息。"""
        h = HTML2Text()
        h.body_width = 90
        msg = self.get_html_msg()
        content = msg['message']
        h.ignore_links = self.text_msg_ignore_links
        msg['message'] = h.handle(content)
        return msg

    @cached_property
    def common_msg(self) -> dict:
        """缓存通用消息模板。"""
        return self.get_common_msg()

    @cached_property
    def text_msg(self) -> dict:
        """缓存纯文本消息。"""
        msg = self.get_text_msg()
        return msg

    @cached_property
    def markdown_msg(self) -> dict:
        """缓存 Markdown 消息。"""
        return self.get_markdown_msg()

    @cached_property
    def html_msg(self) -> dict:
        """缓存 HTML 消息。"""
        msg = self.get_html_msg()
        return msg

    @cached_property
    def html_msg_with_sign(self) -> dict:
        """缓存带签名的 HTML 消息。"""
        msg = self.get_html_msg()
        msg['message'] = textwrap.dedent("""
        {}
        <small>
        <br />
        —
        <br />
        {}
        </small>
        """).format(msg['message'], self.signature)
        return msg

    @cached_property
    def text_msg_with_sign(self) -> dict:
        """缓存带签名的纯文本消息。"""
        msg = self.get_text_msg()
        msg['message'] = textwrap.dedent("""
        {}
        —
        {}
        """).format(msg['message'], self.signature)
        return msg

    @cached_property
    def signature(self) -> str:
        """消息签名。"""
        return 'Xadmin Server'

    # --------------------------------------------------------------
    # 支持不同发送消息的方式定义自己的消息内容，比如有些支持 html 标签
    def get_dingtalk_msg(self) -> dict:
        """返回钉钉消息内容，附加时间后缀以避免重复。"""
        # 钉钉相同的消息一天只能发一次，所以给所有消息添加基于时间的序号，使他们不相同
        message = self.markdown_msg['message']
        time = local_now().strftime('%Y-%m-%d %H:%M:%S')
        suffix = '\n{}: {}'.format(_('Time'), time)

        return {
            'subject': self.markdown_msg['subject'],
            'message': message + suffix
        }

    def get_email_msg(self) -> dict:
        """返回邮件消息内容。"""
        return self.html_msg_with_sign

    def get_site_msg_msg(self) -> dict:
        """返回站内信消息内容。"""
        return self.html_msg

    def get_sms_msg(self) -> dict:
        """返回短信消息内容。"""
        return self.text_msg_with_sign

    @classmethod
    def get_all_sub_messages(cls) -> List[type]:
        """返回所有消息子类列表。"""

        def get_subclasses(cls: type) -> list:
            """returns all subclasses of argument, cls"""
            if issubclass(cls, type):
                subclasses = cls.__subclasses__(cls)
            else:
                subclasses = cls.__subclasses__()
            for subclass in subclasses:
                subclasses.extend(get_subclasses(subclass))
            return subclasses

        messages_cls = get_subclasses(cls)
        return messages_cls

    @classmethod
    def test_all_messages(cls, ding: bool = True, wecom: bool = False) -> None:
        """测试所有消息子类的发送功能。"""
        messages_cls = cls.get_all_sub_messages()

        for _cls in messages_cls:
            try:
                _cls.send_test_msg(ding=ding, wecom=wecom)
            except NotImplementedError:
                continue


class SystemMessage(Message):
    """系统消息基类，发布消息时从系统订阅中获取接收用户。"""

    def publish(self, is_async: bool = False) -> None:
        """发布系统消息，根据订阅配置选择后端并发送。"""
        subscription = SystemMsgSubscription.objects.get(
            message_type=self.get_message_type()
        )

        # 只发送当前有效后端
        receive_backends = subscription.receive_backends
        receive_backends = BACKEND.filter_enable_backends(receive_backends)

        receive_user_ids = subscription.users.values_list('pk', flat=True).all()
        if not receive_user_ids:
            logger.warning(f"send system msg failed. No receive users found for {self}")
            return
        backends_msg_mapper = self.get_backend_msg_mapper(receive_backends)
        if is_async:
            publish_task.delay(receive_user_ids, backends_msg_mapper)
        else:
            self.send_msg(receive_user_ids, backends_msg_mapper)

    @classmethod
    def post_insert_to_db(cls, subscription: SystemMsgSubscription) -> None:
        """订阅记录插入数据库后的回调，子类可覆写。"""
        pass

    @classmethod
    def gen_test_msg(cls):
        """生成测试消息，子类必须实现。"""
        raise NotImplementedError


class UserMessage(Message):
    """用户消息基类，发布消息时从用户订阅中获取接收后端。"""

    user: UserInfo

    def __init__(self, user: UserInfo) -> None:
        """初始化用户消息。

        Args:
            user: 接收用户对象。
        """
        self.user = user

    def publish(self, is_async: bool = False) -> None:
        """发送消息到用户配置的接收方式上。"""
        subscription = UserMsgSubscription.objects.filter(user=self.user, message_type=self.get_message_type()).first()
        if subscription:
            receive_backends = subscription.receive_backends
            receive_backends = BACKEND.filter_enable_backends(receive_backends)
        else:
            receive_backends = []

        backends_msg_mapper = self.get_backend_msg_mapper(receive_backends)
        receive_user_ids = [self.user.id]
        if is_async:
            publish_task.delay(receive_user_ids, backends_msg_mapper)
        else:
            self.send_msg(receive_user_ids, backends_msg_mapper)

    @classmethod
    def get_test_user(cls) -> UserInfo:
        """返回第一个用户用于测试。"""
        from apps.system.models import UserInfo
        return UserInfo.objects.all().first()

    @classmethod
    def gen_test_msg(cls):
        """生成测试消息，子类必须实现。"""
        raise NotImplementedError
