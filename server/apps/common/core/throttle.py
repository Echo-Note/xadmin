#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : throttle
# author : ly_13
# date : 6/2/2023
"""接口访问频率限制器，按业务场景划分限流范围。"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class RegisterThrottle(AnonRateThrottle):
    """注册接口匿名用户限流器。"""

    scope = 'register'


class ResetPasswordThrottle(AnonRateThrottle):
    """重置密码接口匿名用户限流器。"""

    scope = 'reset_password'


class LoginThrottle(AnonRateThrottle):
    """登录接口匿名用户限流器。"""

    scope = 'login'


class UploadThrottle(UserRateThrottle):
    """上传速率限制"""

    scope = 'upload'


class Download1Throttle(UserRateThrottle):
    """下载速率限制"""

    scope = 'download1'


class Download2Throttle(UserRateThrottle):
    """下载速率限制"""

    scope = 'download2'
