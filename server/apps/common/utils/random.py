#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : random
# author : ly_13
# date : 12/10/2024
"""随机数据生成工具模块。"""

import random
import secrets
import socket
import string
import struct
from datetime import datetime

string_punctuation = '!#$%&()*+,-.:;<=?@[]_~'


def random_datetime(date_start: datetime, date_end: datetime) -> datetime:
    """在两个时间点之间生成随机时间。

    Args:
        date_start: 起始时间。
        date_end: 结束时间。

    Returns:
        起始与结束之间的随机时间。
    """
    random_delta = (date_end - date_start) * random.random()
    return date_start + random_delta


def random_ip() -> str:
    """生成随机 IPv4 地址。"""
    return socket.inet_ntoa(struct.pack('>I', random.randint(1, 0xffffffff)))


def random_replace_char(seq: list[str], chars: str, length: int) -> list[str]:
    """随机替换序列中的指定数量字符。

    Args:
        seq: 待替换的字符序列。
        chars: 可选替换字符集。
        length: 替换字符数量。

    Returns:
        替换后的字符序列。
    """
    using_index = set()

    while length > 0:
        index = secrets.randbelow(len(seq) - 1)
        if index in using_index or index == 0:
            continue
        seq[index] = secrets.choice(chars)
        using_index.add(index)
        length -= 1
    return seq


def remove_exclude_char(s: str, exclude_chars: str) -> str:
    """从字符串中移除指定字符。

    Args:
        s: 原始字符串。
        exclude_chars: 需要移除的字符集合。

    Returns:
        移除指定字符后的字符串。
    """
    for i in exclude_chars:
        s = s.replace(i, '')
    return s


def random_string(
        length: int, lower: bool = True, upper: bool = True, digit: bool = True,
        special_char: bool = False, exclude_chars: str = '', symbols: str = string_punctuation
) -> str:
    """生成指定长度和字符组成的随机字符串。

    Args:
        length: 字符串长度，最小为 4。
        lower: 是否包含小写字母。
        upper: 是否包含大写字母。
        digit: 是否包含数字。
        special_char: 是否包含特殊字符。
        exclude_chars: 需排除的字符。
        symbols: 特殊字符集。

    Returns:
        生成的随机字符串。
    """
    if not any([lower, upper, digit]):
        raise ValueError('At least one of `lower`, `upper`, `digit` must be `True`')
    if length < 4:
        raise ValueError('The length of the string must be greater than 3')

    char_list = []
    if lower:
        lower_chars = remove_exclude_char(string.ascii_lowercase, exclude_chars)
        if not lower_chars:
            raise ValueError('After excluding characters, no lowercase letters are available.')
        char_list.append(lower_chars)

    if upper:
        upper_chars = remove_exclude_char(string.ascii_uppercase, exclude_chars)
        if not upper_chars:
            raise ValueError('After excluding characters, no uppercase letters are available.')
        char_list.append(upper_chars)

    if digit:
        digit_chars = remove_exclude_char(string.digits, exclude_chars)
        if not digit_chars:
            raise ValueError('After excluding characters, no digits are available.')
        char_list.append(digit_chars)

    secret_chars = [secrets.choice(chars) for chars in char_list]

    all_chars = ''.join(char_list)

    remaining_length = length - len(secret_chars)
    seq = [secrets.choice(all_chars) for _ in range(remaining_length)]

    if special_char:
        special_chars = remove_exclude_char(symbols, exclude_chars)
        if not special_chars:
            raise ValueError('After excluding characters, no special characters are available.')
        symbol_num = length // 16 + 1
        seq = random_replace_char(seq, special_chars, symbol_num)
    secret_chars += seq

    secrets.SystemRandom().shuffle(secret_chars)
    return ''.join(secret_chars)
