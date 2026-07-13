"""系统应用通知消息。"""

from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request

from apps.common.utils.request import get_request_ip, get_browser
from apps.common.utils.timezone import local_now_display
from apps.notifications.notifications import UserMessage
from apps.system.models import UserInfo


class DifferentCityLoginMessage(UserMessage):
    """异地登录提醒消息。"""

    category = 'AccountSecurity'
    category_label = _('Account Security')
    message_type_label = _('Different city login reminder')

    def __init__(self, user: UserInfo, ip: str, city: str) -> None:
        """初始化异地登录提醒消息。

        Args:
            user: 用户对象。
            ip: 登录 IP 地址。
            city: 登录城市。
        """
        self.ip = ip
        self.city = city
        super().__init__(user)

    def get_html_msg(self) -> dict:
        """生成异地登录提醒的 HTML 消息内容。

        Returns:
            包含主题和正文的字典。
        """
        now = local_now_display()
        subject = _('Different city login reminder')
        context = dict(
            subject=subject,
            name=self.user.nickname,
            username=self.user.username,
            ip=self.ip,
            time=now,
            city=self.city,
        )
        message = render_to_string('notify/msg_different_city.html', context)
        return {
            'subject': subject,
            'message': message
        }

    @classmethod
    def gen_test_msg(cls) -> 'DifferentCityLoginMessage':
        """生成测试消息实例。

        Returns:
            包含测试数据的消息实例。
        """
        from apps.system.models import UserInfo
        user = UserInfo.objects.first()
        ip = '8.8.8.8'
        city = '洛杉矶'
        return cls(user, ip, city)


class ResetPasswordSuccessMsg(UserMessage):
    """密码重置成功通知消息。"""

    category = 'AccountSecurity'
    category_label = _('Account Security')
    message_type_label = _('Reset password reminder')

    def __init__(self, user: UserInfo, request: Request) -> None:
        """初始化密码重置成功消息。

        Args:
            user: 用户对象。
            request: HTTP 请求对象。
        """
        super().__init__(user)
        self.ip_address = get_request_ip(request)
        self.browser = get_browser(request)

    def get_html_msg(self) -> dict:
        """生成密码重置成功的 HTML 消息内容。

        Returns:
            包含主题和正文的字典。
        """
        user = self.user

        subject = _('Reset password success')
        context = {
            'name': user.nickname,
            'username': user.username,
            'ip_address': self.ip_address,
            'browser': self.browser,
        }
        message = render_to_string('notify/msg_rest_password_success.html', context)
        return {
            'subject': subject,
            'message': message
        }

    @classmethod
    def gen_test_msg(cls) -> None:
        """生成测试消息实例（暂不实现）。"""
        pass
