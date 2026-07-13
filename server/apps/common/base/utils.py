#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : utils
# author : ly_13
# date : 6/2/2023
"""通用基础工具模块，提供 AES 加解密、选项字典转换、菜单树构建及文件操作等工具函数。"""


import base64
import hashlib
import os
from collections.abc import Iterable
from typing import Any

from Cryptodome import Random
from Cryptodome.Cipher import AES
from django.conf import settings
from django.forms.models import ModelChoiceIteratorValue

from apps.common.utils import get_logger

logger = get_logger(__name__)


class AESCipher(object):
    """AES-CBC 加密器，使用 SHA256 派生密钥进行加解密。"""

    def __init__(self, key: str) -> None:
        """初始化加密器，根据传入密钥生成 SHA256 摘要作为实际密钥。

        Args:
            key: 原始密钥字符串。
        """
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw: bytes | str) -> bytes:
        """加密数据，返回 Base64 编码的密文。

        Args:
            raw: 待加密的原始数据，可为字符串或字节。

        Returns:
            Base64 编码的密文字节串。
        """
        raw = self._pack_data(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc: str | bytes) -> str:
        """解密 Base64 编码的密文，返回原始字符串。

        Args:
            enc: Base64 编码的密文，可为字符串或字节。

        Returns:
            解密后的原始字符串。
        """
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpack_data(cipher.decrypt(enc[AES.block_size:]))

    @staticmethod
    def _pack_data(s: bytes | str) -> bytes:
        """对数据进行 PKCS7 风格的填充，使其长度为 AES 块大小的整数倍。

        Args:
            s: 待填充的数据，可为字符串或字节。

        Returns:
            填充后的字节数据。
        """
        if isinstance(s, str):
            s = s.encode('utf-8')
        return s + ((AES.block_size - len(s) % AES.block_size) * chr(AES.block_size - len(s) % AES.block_size)).encode(
            'utf-8')

    @staticmethod
    def _unpack_data(s: bytes) -> str:
        """去除 PKCS7 风格的填充，还原原始数据。

        Args:
            s: 带填充的字节数据。

        Returns:
            去填充后的字符串。
        """
        data = s[:-ord(s[len(s) - 1:])]
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return data


def get_signer() -> AESCipher:
    """使用 Django SECRET_KEY 创建 AES 加密器实例。

    Returns:
        基于 SECRET_KEY 的 AESCipher 实例。
    """
    s = AESCipher(settings.SECRET_KEY)
    return s


signer: AESCipher = get_signer()


class AesBaseCrypt(object):
    """基于类名派生密钥的 AES 加密基类。"""

    def __init__(self) -> None:
        """初始化加密器，以子类类名作为密钥创建 AESCipher 实例。"""
        self.cipher = AESCipher(self.__class__.__name__)

    def set_encrypt_uid(self, key: str) -> str:
        """加密指定键值，返回 Base64 编码的字符串。

        Args:
            key: 待加密的原始键值字符串。

        Returns:
            加密后的 Base64 字符串。
        """
        return self.cipher.encrypt(key.encode('utf-8')).decode('utf-8')

    def get_decrypt_uid(self, enc: str) -> str | None:
        """解密 Base64 编码的字符串。

        Args:
            enc: Base64 编码的密文字符串。

        Returns:
            解密后的原始字符串，解密失败时返回 None。
        """
        try:
            return self.cipher.decrypt(enc)
        except Exception as e:
            logger.warning(f'decrypt {enc} failed. exception:{e}')


def get_choices_dict(
    choices: Iterable,
    disabled_choices: list | None = None,
) -> list[dict]:
    """将 Django 选项列表转换为前端友好的字典列表。

    Args:
        choices: Django 表单选项可迭代对象。
        disabled_choices: 需要标记为禁用的选项值列表。

    Returns:
        包含 ``value``、``label`` 及可选 ``disabled`` 字段的字典列表。
    """
    result = []
    choices_org_list = list(choices)
    for choice in choices_org_list:
        c0 = choice[0]
        if isinstance(c0, ModelChoiceIteratorValue):
            c0 = str(c0)
        val = {'value': c0, 'label': choice[1]}
        if disabled_choices and isinstance(disabled_choices, list) and choice[0] in disabled_choices:
            val['disabled'] = True
        result.append(val)
    return result


def get_choices_name_from_key(choices: Iterable, key: Any) -> str:
    """根据选项值从选项列表中查找对应的显示名称。

    Args:
        choices: Django 表单选项可迭代对象。
        key: 待查找的选项值。

    Returns:
        选项值对应的显示名称，未找到时返回空字符串。
    """
    choices_org_list = list(choices)
    for choice in choices_org_list:
        if choice[0] == key:
            return choice[1]
    return ''


def redis_key_func(key: str, key_prefix: str, version: int) -> str:
    """默认的 Redis 缓存键生成函数。

    构造所有缓存方法使用的键。默认直接返回原始键。
    可通过 ``KEY_FUNCTION`` 指定自定义键生成函数。

    Args:
        key: 原始缓存键。
        key_prefix: 键前缀。
        version: 缓存版本号。

    Returns:
        生成后的缓存键字符串。
    """
    return key


def redis_reverse_key_func(key: str) -> str:
    """Redis 缓存键反向解析函数，返回原始键。

    Args:
        key: 缓存键字符串。

    Returns:
        原始键字符串。
    """
    return key


def menu_list_to_tree(data: list, root_field: str = 'parent') -> list:
    """将权限菜单扁平列表转换为树状结构。"""
    mapping: dict = dict(zip([str(i['pk']) for i in data], data))

    # 树容器
    container: list = []

    for d in data:
        # 如果找不到父级项，则是根节点
        parent = d.get(root_field)
        if isinstance(parent, dict) and 'pk' in parent:
            parent = parent.get('pk')
        parent: dict = mapping.get(str(parent))
        if parent is None:
            container.append(d)
        else:
            children: list = parent.get('children')
            if not children:
                children = []
            children.append(d)
            parent.update({'children': children, 'count': len(children)})
    return container


def format_menu_meta(meta: dict) -> dict:
    """从菜单元信息中提取前端所需字段。

    Args:
        meta: 原始菜单元信息字典。

    Returns:
        仅包含 ``icon``、``title``、``rank``、``showLink`` 字段的字典。
    """
    new_meta = {}
    for key in ['icon', 'title', 'rank', 'showLink']:
        new_meta[key] = meta.get(key)
    return new_meta


def format_menu_data(data: list) -> list:
    """将菜单树数据格式化为前端路由所需结构。

    对无子节点的菜单项包装一层默认路由父级；有子节点的直接保留。

    Args:
        data: 菜单树列表。

    Returns:
        格式化后的路由列表。
    """
    new_result = []
    for d in data:
        if d.get('count', -1) < 1:
            route = {
                'path': f"/default{d.get('path')}",
                'title': d.get('title'),
                'meta': format_menu_meta(d.get('meta', {})),
                'children': [d]
            }
        else:
            route = d
        new_result.append(route)
    return new_result


def remove_file(name: str) -> None:
    """删除指定文件或空目录，失败时仅记录日志。

    Args:
        name: 文件或目录路径。
    """
    try:
        if os.path.isdir(name):
            os.rmdir(name)
        else:
            os.remove(name)
        logger.info(f"remove {name} success")
    except Exception as e:
        # FileNotFoundError is raised if the file or directory was removed
        # concurrently.
        logger.warning(f"remove {name} failed {e}")


class AESCipherV2(object):
    """与前端 CryptoJS AES 加解密兼容的加密器（OpenSSL Salted 格式）。

    前端操作示例::

        import CryptoJS from "crypto-js";

        export function AesEncrypted(key: string, msg: string): string {
          return CryptoJS.AES.encrypt(msg, key).toString();
        }

        export function AesDecrypted(key: string, encryptedMessage: string): string {
          return CryptoJS.AES.decrypt(encryptedMessage, key).toString(
            CryptoJS.enc.Utf8
          );
        }
    """

    def __init__(self, key: str | bytes) -> None:
        """初始化加密器，将密钥统一转为字节。

        Args:
            key: 原始密钥，可为字符串或字节。
        """
        self.key = key.encode('utf-8') if isinstance(key, str) else key

    def _make_key(self, salt: bytes, output: int = 48) -> bytes:
        """根据盐值派生指定长度的密钥（兼容 OpenSSL EVP_BytesToKey）。

        Args:
            salt: 盐值字节串。
            output: 目标密钥长度，默认为 48（32 字节 key + 16 字节 IV）。

        Returns:
            派生后的密钥字节串。
        """
        key = hashlib.md5(self.key + salt).digest()
        final_key = key
        while len(final_key) < output:
            key = hashlib.md5(key + self.key + salt).digest()
            final_key += key
        return final_key[:output]

    def encrypt(self, raw: bytes | str) -> bytes:
        """加密数据，返回 Base64 编码的 OpenSSL Salted 格式密文。

        Args:
            raw: 待加密的原始数据，可为字符串或字节。

        Returns:
            Base64 编码的密文字节串。
        """
        salt = Random.new().read(8)
        key_iv = self._make_key(salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return base64.b64encode(b"Salted__" + salt + cipher.encrypt(self._pack_data(raw)))

    def decrypt(self, enc: str | bytes) -> str:
        """解密 Base64 编密的 OpenSSL Salted 格式密文。

        Args:
            enc: Base64 编码的密文，可为字符串或字节。

        Returns:
            解密后的原始字符串；若格式不匹配则返回空字符串。
        """
        data = base64.b64decode(enc)
        if data[:8] != b'Salted__':
            return ''
        salt = data[8:16]
        key_iv = self._make_key(salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return self._unpack_data(cipher.decrypt(data[AES.block_size:]))

    @staticmethod
    def _pack_data(s: bytes | str) -> bytes:
        """对数据进行 PKCS7 风格的填充，使其长度为 AES 块大小的整数倍。

        Args:
            s: 待填充的数据，可为字符串或字节。

        Returns:
            填充后的字节数据。
        """
        return s + ((AES.block_size - len(s) % AES.block_size) * chr(AES.block_size - len(s) % AES.block_size)).encode(
            'utf-8')

    @staticmethod
    def _unpack_data(s: bytes) -> str:
        """去除 PKCS7 风格的填充，还原原始数据。

        Args:
            s: 带填充的字节数据。

        Returns:
            去填充后的字符串。
        """
        data = s[:-ord(s[len(s) - 1:])]
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return data
