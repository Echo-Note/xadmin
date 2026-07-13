#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : sms
# author : ly_13
# date : 8/6/2024
"""短信设置序列化器定义。"""

import phonenumbers
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.common.core.fields import PhoneField
from apps.common.core.validators import PhoneValidator
from apps.common.sdk.sms.endpoint import BACKENDS


class SMSSettingSerializer(serializers.Serializer):
    """短信服务设置序列化器。"""

    SMS_ENABLED = serializers.BooleanField(
        default=False, label=_('SMS'), help_text=_('Enable Short Message Service (SMS)')
    )
    SMS_BACKEND = serializers.ChoiceField(choices=BACKENDS.choices, default=BACKENDS.ALIBABA, label=_('Provider'),
                                          help_text=_('Short Message Service (SMS) provider or protocol'))


class BaseSMSSettingSerializer(serializers.Serializer):
    """短信设置基类序列化器，包含测试手机号字段。"""

    PREFIX_TITLE = _('SMS')

    SMS_TEST_PHONE = PhoneField(
        validators=[PhoneValidator()], required=False, allow_blank=True, allow_null=True,
        label=_('Phone'), help_text=_("The phone is used for testing the SMS server's connectivity")
    )

    def post_save(self) -> None:
        """保存后对测试手机号进行格式化处理。"""
        value = self._data['SMS_TEST_PHONE']
        if isinstance(value, dict):
            return
        try:
            phone = phonenumbers.parse(value, 'CN')
            value = {'code': '+%s' % phone.country_code, 'phone': phone.national_number}
        except phonenumbers.NumberParseException:
            value = {'code': '+86', 'phone': value}
        self._data['SMS_TEST_PHONE'] = value


class AlibabaSMSSettingSerializer(BaseSMSSettingSerializer):
    """阿里云短信设置序列化器。"""

    ALIBABA_ACCESS_KEY_ID = serializers.CharField(max_length=256, required=True, label='Access Key ID')
    ALIBABA_ACCESS_KEY_SECRET = serializers.CharField(
        max_length=256, required=False, label='Access Key Secret', write_only=True
    )
    ALIBABA_VERIFY_SIGN_NAME = serializers.CharField(max_length=256, required=True, label=_('Signature'))
    ALIBABA_VERIFY_TEMPLATE_CODE = serializers.CharField(max_length=256, required=True, label=_('Template code'))


class SMSBackendSerializer(serializers.Serializer):
    """短信后端序列化器。"""

    name = serializers.CharField(max_length=256, required=True, label=_('Name'))
    label = serializers.CharField(max_length=256, required=True, label=_('Label'))
