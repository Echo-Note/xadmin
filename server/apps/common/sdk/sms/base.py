#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : base
# author : ly_13
# date : 8/6/2024
"""短信客户端基类。"""
from typing import NoReturn

from apps.common.utils import get_logger

logger = get_logger(__name__)


class BaseSMSClient:
    """
    短信终端的基类
    """

    SIGN_AND_TMPL_SETTING_FIELD_PREFIX: str

    @classmethod
    def new_from_settings(cls) -> 'BaseSMSClient':
        """从配置创建短信客户端实例，子类实现。"""
        raise NotImplementedError

    def send_sms(
        self, phone_numbers: list, sign_name: str, template_code: str, template_param: dict, **kwargs
    ) -> NoReturn:
        """发送短信，子类实现。"""
        raise NotImplementedError

    @staticmethod
    def need_pre_check() -> bool:
        """是否需要预检查签名与模板配置。"""
        return True

