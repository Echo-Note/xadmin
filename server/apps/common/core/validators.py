#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : validators
# author : ly_13
# date : 8/6/2024
"""自定义字段校验器集合。"""

import phonenumbers
from django.utils.translation import gettext_lazy as _
from phonenumbers import NumberParseException
from rest_framework import serializers


class PhoneValidator:
    """手机号格式校验器，基于 ``phonenumbers`` 库解析中国大陆手机号。"""

    message = _('The phone number format is incorrect')

    def __call__(self, value: str) -> None:
        """校验手机号格式是否合法。

        Args:
            value: 待校验的手机号字符串。

        Raises:
            serializers.ValidationError: 当手机号格式不合法时抛出。
        """
        if not value:
            return

        try:
            phone = phonenumbers.parse(value, 'CN')
            valid = phonenumbers.is_valid_number(phone)
        except NumberParseException:
            valid = False

        if not valid:
            raise serializers.ValidationError(self.message)
