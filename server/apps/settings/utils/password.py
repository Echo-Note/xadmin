#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : password
# author : ly_13
# date : 8/10/2024
"""密码规则校验工具。"""

import re
from typing import List

from django.conf import settings

from apps.system.models import UserInfo


def get_password_check_rules(user: UserInfo) -> List[dict]:
    """根据用户身份获取适用的密码校验规则。

    Args:
        user: 用户对象。

    Returns:
        密码校验规则列表。
    """
    check_rules = []
    for rule in settings.SECURITY_PASSWORD_RULES:
        if user.is_superuser and rule == 'SECURITY_PASSWORD_MIN_LENGTH':
            rule = 'SECURITY_ADMIN_USER_PASSWORD_MIN_LENGTH'
        value = getattr(settings, rule)
        if not value:
            continue
        check_rules.append({'key': rule, 'value': int(value)})
    return check_rules


def check_password_rules(password: str, is_super_admin: bool = False) -> bool:
    """校验密码是否符合安全规则。

    Args:
        password: 待校验的密码。
        is_super_admin: 是否为超级管理员。

    Returns:
        密码是否符合规则。
    """
    pattern = r"^"
    if settings.SECURITY_PASSWORD_UPPER_CASE:
        pattern += r'(?=.*[A-Z])'
    if settings.SECURITY_PASSWORD_LOWER_CASE:
        pattern += r'(?=.*[a-z])'
    if settings.SECURITY_PASSWORD_NUMBER:
        pattern += r'(?=.*\d)'
    if settings.SECURITY_PASSWORD_SPECIAL_CHAR:
        pattern += r'(?=.*[`~!@#$%^&*()\-=_+\[\]{}|;:\'",.<>/?])'
    pattern += r'[a-zA-Z\d`~!@#\$%\^&\*\(\)-=_\+\[\]\{\}\|;:\'\",\.<>\/\?]'
    if is_super_admin:
        min_length = settings.SECURITY_ADMIN_USER_PASSWORD_MIN_LENGTH
    else:
        min_length = settings.SECURITY_PASSWORD_MIN_LENGTH
    pattern += '.{' + str(min_length - 1) + ',}$'
    match_obj = re.match(pattern, password)
    return bool(match_obj)
