#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : aes
# author : ly_13
# date : 1/17/2024
"""AES 加密字段。"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.base.utils import AESCipher


class AESField(models.Field):
    """AES 加密字段基类。"""

    def __init__(self, *args, **kwargs) -> None:
        """初始化 AES 字段，设置加密前缀与加密器。

        Args:
            args: 位置参数，透传给父类。
            kwargs: 关键字参数，可含 prefix 指定加密前缀。
        """
        if 'prefix' in kwargs:
            self.prefix = kwargs['prefix']
            del kwargs['prefix']
        else:
            self.prefix = "aes:::"
        self.cipher = AESCipher(settings.SECRET_KEY)
        super(AESField, self).__init__(*args, **kwargs)

    def deconstruct(self) -> tuple:
        """返回字段的构造参数，用于迁移文件生成。"""
        name, path, args, kwargs = super(AESField, self).deconstruct()
        if self.prefix != "aes:::":
            kwargs['prefix'] = self.prefix
        return name, path, args, kwargs

    def from_db_value(self, value: str | bytes | None, *args, **kwargs) -> str | bytes | None:
        """从数据库读取时解密字段值。

        Args:
            value: 数据库原始值。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            解密后的值，原始值为 None 时返回 None。
        """
        if value is None:
            return value
        if value.startswith(self.prefix):
            value = value[len(self.prefix):]
            if isinstance(value, str):
                value = value.encode('utf-8')
            value = self.cipher.decrypt(value)
        return value

    def to_python(self, value: str | bytes | None) -> str | bytes | None:
        """将值转换为 Python 对象，解密带前缀的值。

        Args:
            value: 原始值。

        Returns:
            解密后的值，原始值为 None 时返回 None。
        """
        if value is None:
            return value
        elif value.startswith(self.prefix):
            value = value[len(self.prefix):]
            if isinstance(value, str):
                value = value.encode('utf-8')
            value = self.cipher.decrypt(value)
        return value

    def get_prep_value(self, value: str | bytes | None) -> str | None:
        """准备写入数据库的值，加密字符串或字节。

        Args:
            value: 原始值。

        Returns:
            加密后的字符串，值为 None 时返回 None。
        """
        if isinstance(value, str):
            value = value.encode('utf-8')
        if isinstance(value, bytes):
            value = self.cipher.encrypt(value)
            value = self.prefix + value.decode('utf-8')
        elif value is not None:
            raise TypeError(_("{} is not a valid value for AESCharField").format(value))
        return value


class AESCharField(AESField, models.CharField):
    """AES 加密的 CharField。"""


class AESTextField(AESField, models.TextField):
    """AES 加密的 TextField。"""

