"""认证相关工具函数。"""

import ipaddress

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from user_agents import parse

from apps.captcha.utils import CaptchaAuth
from apps.common.base.utils import AESCipherV2
from apps.common.utils.ip import get_ip_city
from apps.common.utils.request import get_request_ip, get_browser, get_os, get_request_ident
from apps.common.utils.token import verify_token_cache
from apps.common.utils.verify_code import TokenTempCache, SendAndVerifyCodeUtil
from apps.settings.utils.security import LoginIpBlockUtil, LoginBlockUtil
from apps.system.models import UserLoginLog, UserInfo
from apps.system.notifications import DifferentCityLoginMessage
from apps.system.serializers.log import LoginLogSerializer


def get_token_lifetime(user_obj: UserInfo) -> dict:
    """获取 JWT 令牌的有效期信息。

    Args:
        user_obj: 用户对象。

    Returns:
        包含 access 和 refresh 令牌有效期的字典。
    """
    access_token_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME')
    refresh_token_lifetime = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME')
    return {
        'access_token_lifetime': int(access_token_lifetime.total_seconds()),
        'refresh_token_lifetime': int(refresh_token_lifetime.total_seconds()),
        # 'username': user_obj.username
    }


def check_captcha(need: bool, captcha_key: str, captcha_code: str) -> bool:
    """校验图片验证码。

    Args:
        need: 是否需要验证码。
        captcha_key: 验证码键。
        captcha_code: 用户输入的验证码。

    Returns:
        校验通过返回 True，否则抛出异常。
    """
    if not need or (captcha_key and CaptchaAuth(captcha_key=captcha_key).valid(captcha_code)):
        return True
    raise APIException(_("Captcha validation failed. Please try again"))


def check_tmp_token(need: bool, token: str, client_id: str, success_once: bool = True) -> bool:
    """校验临时令牌。

    Args:
        need: 是否需要令牌校验。
        token: 临时令牌。
        client_id: 客户端标识。
        success_once: 是否一次性有效。

    Returns:
        校验通过返回 True，否则抛出异常。
    """
    if not need or (client_id and token and verify_token_cache(token, client_id, success_once)):
        return True
    raise APIException(_("Temporary Token validation failed. Please try again"))


def check_token_and_captcha(request: Request, token_enable: bool, captcha_enable: bool,
                           success_once: bool = True) -> tuple[str, str]:
    """同时校验临时令牌和图片验证码。

    Args:
        request: HTTP 请求对象。
        token_enable: 是否启用令牌校验。
        captcha_enable: 是否启用验证码校验。
        success_once: 令牌是否一次性有效。

    Returns:
        客户端标识和令牌的元组。
    """
    client_id = get_request_ident(request)
    token = request.data.get('token')
    captcha_key = request.data.get('captcha_key')
    captcha_code = request.data.get('captcha_code')

    check_tmp_token(token_enable, token, client_id, success_once)
    check_captcha(captcha_enable, captcha_key, captcha_code)
    return client_id, token


def get_username_password(need: bool, request: Request, token: str) -> tuple[str, str]:
    """从请求中获取用户名和密码，根据配置进行解密。

    Args:
        need: 是否需要解密。
        request: HTTP 请求对象。
        token: 解密用的令牌。

    Returns:
        用户名和密码的元组。
    """
    username = request.data.get('username')
    password = request.data.get('password')
    if need:
        username = AESCipherV2(token).decrypt(username)
        password = AESCipherV2(token).decrypt(password)
    return username, password


def check_is_block(username: str, ipaddr: str, ip_block: type = LoginIpBlockUtil,
                   login_block: type = LoginBlockUtil) -> None:
    """检查用户或 IP 是否被封锁。

    Args:
        username: 用户名。
        ipaddr: IP 地址。
        ip_block: IP 封锁工具类。
        login_block: 用户封锁工具类。

    Raises:
        APIException: 当用户或 IP 被封锁时。
    """
    if ip_block and ip_block(ipaddr).is_block():
        ip_block(ipaddr).set_block_if_need()
        raise APIException(_("The address has been locked (please contact admin to unlock it or try"
                             " again after {} minutes)").format(settings.SECURITY_LOGIN_IP_LIMIT_TIME))

    if login_block and login_block(username, ipaddr).is_block():
        raise APIException(_("The account has been locked (please contact admin to unlock it or try"
                             " again after {} minutes)").format(settings.SECURITY_LOGIN_LIMIT_TIME))


def save_login_log(request: Request, login_type: UserLoginLog.LoginTypeChoices = UserLoginLog.LoginTypeChoices.USERNAME,
                   status: bool = True, channel_name: str = '') -> None:
    """保存登录日志。

    Args:
        request: HTTP 请求对象。
        login_type: 登录方式。
        status: 登录是否成功。
        channel_name: WebSocket 通道名称。
    """
    login_ip = get_request_ip(request) if request else ''
    login_ip = login_ip or '0.0.0.0'
    login_city = get_ip_city(login_ip) or _("Unknown")
    data = {
        'ipaddress': login_ip,
        'city': str(login_city),
        'browser': get_browser(request),
        'system': get_os(request),
        'channel_name': channel_name or getattr(request, "channel_name", ""),
        'status': status,
        'agent': str(parse(request.META['HTTP_USER_AGENT'])),
        'login_type': login_type
    }
    serializer = LoginLogSerializer(data=data, ignore_field_permission=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()


def verify_sms_email_code(request: Request, block_utils: type) -> tuple[str, str, str]:
    """验证短信/邮箱验证码并返回查询信息。

    Args:
        request: HTTP 请求对象。
        block_utils: 封锁工具类。

    Returns:
        查询字段名、目标值和验证令牌的元组。
    """
    verify_token = request.data.get('verify_token')
    verify_code = request.data.get('verify_code')
    ipaddr = get_request_ip(request)
    ip_block = LoginIpBlockUtil(ipaddr)

    if not verify_token or not verify_code:
        raise APIException(_("Operation failed. Abnormal data"))

    data = TokenTempCache.validate_cache_token(verify_token)
    if not data:
        ip_block.set_block_if_need()
        raise APIException(_('Token is invalid or expired'))

    target = data.get('target')
    query_key = data.get('query_key')
    check_is_block(target, ipaddr, login_block=block_utils)
    block_util = block_utils(target, ipaddr)

    try:
        SendAndVerifyCodeUtil(target).verify(verify_code)
    except Exception as e:
        block_util.incr_failed_count()
        ip_block.set_block_if_need()
        request.user = UserInfo.objects.filter(**{query_key: target}).first()
        save_login_log(request, login_type=UserLoginLog.get_login_type(query_key), status=False)
        times_remainder = block_util.get_remainder_times()
        if times_remainder > 0:
            detail = _(
                "{error} please enter it again. "
                "You can also try {times_try} times "
                "(The account will be temporarily locked for {block_time} minutes)"
            ).format(times_try=times_remainder, block_time=settings.SECURITY_LOGIN_LIMIT_TIME, error=str(e))
        else:
            detail = _("The account has been locked (please contact admin to unlock it or try"
                       " again after {} minutes)").format(settings.SECURITY_LOGIN_LIMIT_TIME)

        raise APIException(detail)

    return query_key, target, verify_token


def check_different_city_login_if_need(user: UserInfo, ipaddr: str) -> None:
    """检查是否异地登录，如果是则发送通知。

    Args:
        user: 用户对象。
        ipaddr: 当前登录 IP 地址。
    """
    if not settings.SECURITY_CHECK_DIFFERENT_CITY_LOGIN or ipaddr == 'unknown':
        return

    city_white = [_('LAN'), 'LAN']
    is_private = ipaddress.ip_address(ipaddr).is_private
    if is_private:
        return
    last_user_login = UserLoginLog.objects.exclude(
        city__in=city_white
    ).filter(creator=user, status=True).first()
    if not last_user_login:
        return

    city = get_ip_city(ipaddr)
    last_city = get_ip_city(last_user_login.ipaddress)
    if city == last_city:
        return

    DifferentCityLoginMessage(user, ipaddr, city).publish_async()
