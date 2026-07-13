#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : token
# author : ly_13
# date : 6/2/2023
"""令牌生成与验证工具模块。"""

import random
import string
import time
import uuid
from typing import Any

from apps.common.cache.storage import RedisCacheBase, TokenManagerCache
from apps.common.utils import get_logger

logger = get_logger(__name__)


def make_token_cache(
    key: str,
    time_limit: int = 60,
    prefix: str = '',
    force_new: bool = False,
    ext_data: Any = None,
) -> str:
    """创建或获取令牌缓存。

    若缓存中已存在有效令牌且未强制刷新，则直接返回；否则生成新令牌并写入缓存。

    Args:
        key: 令牌关联的业务键。
        time_limit: 缓存有效期（秒）。
        prefix: 缓存键前缀。
        force_new: 是否强制生成新令牌。
        ext_data: 扩展数据，随令牌一同缓存。

    Returns:
        令牌字符串。
    """
    token_cache = TokenManagerCache(prefix, key)
    token_key, token = token_cache.get_storage_key_and_cache()
    if token and not force_new:
        logger.debug(f'make_token cache exists. token:{token} force_new:{force_new} token_key:{token_key}')
        return token
    else:
        random_str = uuid.uuid1().__str__().split('-')[0:-1]
        user_ran_str = uuid.uuid5(uuid.NAMESPACE_DNS, key).__str__().split('-')
        user_ran_str.extend(random_str)
        token = f'tmp_token_{"".join(user_ran_str)}'

        token_cache.set_storage_cache({
            'atime': time.time() + time_limit,
            'data': key
        }, time_limit)
        RedisCacheBase(token).set_storage_cache({
            'atime': time.time() + time_limit,
            'data': key,
            'ext_data': ext_data
        }, time_limit)
        token_cache.set_storage_cache(token, time_limit - 1)
        logger.debug(f'make_token cache not exists. token:{token} force_new:{force_new} token_key:{token_key}')
        return token


def verify_token_cache(token: str, key: str, success_once: bool = False) -> dict | bool:
    """验证令牌缓存是否有效。

    Args:
        token: 待验证的令牌字符串。
        key: 令牌关联的业务键。
        success_once: 验证成功后是否立即删除缓存。

    Returns:
        验证成功返回缓存数据字典，失败返回 False。
    """
    try:
        token_cache = RedisCacheBase(token)
        token, values = token_cache.get_storage_key_and_cache()
        if values and key == values.get('data', None):
            logger.debug(f'verify_token token:{token}  key:{key} success')
            if success_once:
                token_cache.del_storage_cache()
            return values
    except Exception as e:
        logger.error(f'verify_token token:{token}  key:{key} failed Exception:{e}')
        return False
    logger.error(f'verify_token token:{token}  key:{key} failed')
    return False


def generate_token_for_medium(medium: str) -> str:
    """根据媒介类型生成对应令牌。

    Args:
        medium: 媒介类型，如 email、wechat、sms。

    Returns:
        生成的令牌字符串。
    """
    if medium == 'email':
        return generate_alphanumeric_token_of_length(32)
    elif medium == 'wechat':
        return 'WeChat'
    else:
        return generate_numeric_token_of_length(6)


def generate_numeric_token_of_length(length: int, random_str: str = '') -> str:
    """生成指定长度的数字令牌。

    Args:
        length: 令牌长度。
        random_str: 额外可选取的字符。

    Returns:
        数字令牌字符串。
    """
    return ''.join([random.choice(string.digits + random_str) for _ in range(length)])


def generate_alphanumeric_token_of_length(length: int) -> str:
    """生成指定长度的字母数字混合令牌。

    Args:
        length: 令牌长度。

    Returns:
        字母数字令牌字符串。
    """
    return ''.join(
        [random.choice(string.digits + string.ascii_lowercase + string.ascii_uppercase) for _ in range(length)])


def generate_good_token_of_length(length: int) -> str:
    """生成指定长度的易辨识令牌（去除易混淆字符）。

    Args:
        length: 令牌长度。

    Returns:
        易辨识令牌字符串。
    """
    ascii_uppercase = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    digits = '23456789'
    return ''.join([random.choice(digits + ascii_uppercase) for _ in range(length)])
