"""日志模型。"""

import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel


class UserLoginLog(DbAuditModel):
    """用户登录日志模型。"""

    class LoginTypeChoices(models.IntegerChoices):
        """登录方式选择。"""

        USERNAME = 0, _('Username and password')
        SMS = 1, _('SMS verification code')
        EMAIL = 2, _('Email verification code')
        WECHAT = 4, _('Wechat scan code')
        WEBSOCKET = 8, _('Websocket')
        UNKNOWN = 9, _('Unknown')

    status = models.BooleanField(default=True, verbose_name=_('Login status'), help_text=_('Whether the login attempt was successful'), db_comment="登录是否成功")
    ipaddress = models.GenericIPAddressField(verbose_name=_('IpAddress'), null=True, blank=True, help_text=_('IP address from which the login request originated'), db_comment="登录IP地址")
    city = models.CharField(max_length=254, verbose_name=_('Login city'), null=True, blank=True, help_text=_('Geographic city resolved from the login IP address'), db_comment="登录城市")
    browser = models.CharField(max_length=64, verbose_name=_('Browser'), null=True, blank=True, help_text=_('Browser information parsed from the user agent string'), db_comment="浏览器信息")
    system = models.CharField(max_length=64, verbose_name=_('System'), null=True, blank=True, help_text=_('Operating system information parsed from the user agent string'), db_comment="操作系统信息")
    agent = models.CharField(max_length=128, verbose_name=_('Agent'), null=True, blank=True, help_text=_('Raw user agent string from the login request header'), db_comment="用户代理字符串")
    channel_name = models.CharField(max_length=128, verbose_name=_('Channel name'), null=True, blank=True, help_text=_('Name of the registration or login channel used'), db_comment="登录渠道名称")
    login_type = models.SmallIntegerField(default=LoginTypeChoices.USERNAME, choices=LoginTypeChoices,
                                          verbose_name=_('Login type'),
                                          help_text=_('Login method: 0-password, 1-SMS, 2-email, 4-WeChat, 8-WebSocket, 9-unknown'),
                                          db_comment="登录方式（0-账密 1-短信 2-邮箱 4-微信 8-WebSocket 9-未知）")

    class Meta:
        """用户登录日志元数据。"""

        verbose_name = _('User login log')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        db_table_comment = "用户登录日志表"

    @staticmethod
    def get_login_type(query_key: str) -> LoginTypeChoices:
        """根据查询关键词获取对应的登录类型。

        Args:
            query_key: 登录方式关键词（email/phone/username）。

        Returns:
            对应的 LoginTypeChoices 枚举值。
        """
        if query_key == 'email':
            login_type = UserLoginLog.LoginTypeChoices.EMAIL
        elif query_key == 'phone':
            login_type = UserLoginLog.LoginTypeChoices.SMS
        elif query_key == 'username':
            login_type = UserLoginLog.LoginTypeChoices.USERNAME
        else:
            login_type = UserLoginLog.LoginTypeChoices.UNKNOWN
        return login_type


class OperationLog(DbAuditModel):
    """操作日志模型，记录 API 请求和响应信息。"""

    module = models.CharField(max_length=64, verbose_name=_('Module'), null=True, blank=True, help_text=_('Name of the API module that handled the request'), db_comment="请求模块")
    path = models.CharField(max_length=400, verbose_name=_('URL path'), null=True, blank=True, help_text=_('Full URL path of the API request'), db_comment="请求URL路径")
    body = models.TextField(verbose_name=_('Request body'), null=True, blank=True, help_text=_('Raw request body content sent by the client'), db_comment="请求体内容")
    method = models.CharField(max_length=8, verbose_name=_('Request method'), null=True, blank=True, help_text=_('HTTP method of the request (GET, POST, PUT, DELETE, etc.)'), db_comment="HTTP请求方法")
    ipaddress = models.GenericIPAddressField(verbose_name=_('IpAddress'), null=True, blank=True, help_text=_('IP address from which the API request originated'), db_comment="请求IP地址")
    browser = models.CharField(max_length=64, verbose_name=_('Browser'), null=True, blank=True, help_text=_('Browser information parsed from the request user agent'), db_comment="浏览器信息")
    system = models.CharField(max_length=64, verbose_name=_('System'), null=True, blank=True, help_text=_('Operating system information parsed from the request user agent'), db_comment="操作系统信息")
    response_code = models.IntegerField(verbose_name=_('Response code'), null=True, blank=True, help_text=_('Business-level response code returned by the API'), db_comment="业务响应码")
    response_result = models.TextField(verbose_name=_('Response result'), null=True, blank=True, help_text=_('Full response body content returned to the client'), db_comment="响应结果内容")
    status_code = models.IntegerField(verbose_name=_('Status code'), null=True, blank=True, help_text=_('HTTP status code of the response (e.g. 200, 404, 500)'), db_comment="HTTP状态码")
    request_uuid = models.UUIDField(verbose_name=_('Request ID'), null=True, blank=True, help_text=_('Unique identifier for tracing this request across services'), db_comment="请求唯一标识ID")
    exec_time = models.FloatField(verbose_name=_('Execution time'), null=True, blank=True, help_text=_('Total execution time of the request in seconds'), db_comment="请求执行耗时（秒）")

    class Meta:
        """操作日志元数据。"""

        verbose_name = _('Operation log')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        db_table_comment = "操作日志表，记录API请求和响应信息"

    def remove_expired(cls, clean_day: int = 30 * 6) -> None:
        """删除指定天数前的操作日志。

        Args:
            clean_day: 保留天数，默认 180 天。
        """
        clean_time = timezone.now() - datetime.timedelta(days=clean_day)
        cls.objects.filter(created_time__lt=clean_time).delete()

    remove_expired = classmethod(remove_expired)
