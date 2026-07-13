#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : redis
# author : ly_13
# date : 6/2/2023
"""Redis 数据结构缓存封装模块，提供列表、集合、有序集合、哈希等操作。"""

import json
import time
from typing import Any

import redis
from django_redis import get_redis_connection

from apps.common.utils import get_logger

logger = get_logger(__name__)


def format_return(data: Any) -> Any:
    """将 Redis 返回的 bytes 或 JSON 字符串反序列化为 Python 对象。

    Args:
        data: 原始数据。

    Returns:
        反序列化后的对象，失败时返回原始数据。
    """
    try:
        if isinstance(data, bytes):
            data = data.decode(encoding='utf-8')
        return json.loads(data)
    except Exception:
        return data


def format_input(data: Any) -> str:
    """将 Python 对象序列化为 JSON 字符串。

    Args:
        data: 待序列化的对象。

    Returns:
        JSON 字符串，失败时返回原始数据。
    """
    try:
        return json.dumps(data)
    except Exception:
        return data


class CacheRedis(object):
    """Redis 缓存基类，封装连接与基础操作。"""

    def __init__(self, key: str) -> None:
        """初始化 Redis 缓存。

        Args:
            key: Redis 缓存键。
        """
        self.connect: redis.Redis = get_redis_connection('default')
        self.key = key

    def lock(self, *args: Any, **kwargs: Any) -> redis.lock.Lock:
        """获取 Redis 分布式锁。

        Args:
            *args: 传递给 lock 的位置参数。
            **kwargs: 传递给 lock 的关键字参数。

        Returns:
            Redis 锁对象。
        """
        return self.connect.lock(f'{self.key}_locker', *args, **kwargs)

    def expire(self, timeout: int | None = None) -> bool:
        """设置键的过期时间。

        Args:
            timeout: 过期时间（秒）。

        Returns:
            操作是否成功。
        """
        return self.connect.expire(self.key, timeout)


class CacheList(CacheRedis):
    """Redis 列表缓存封装。"""

    def __init__(self, key: str, max_size: int = 1024, timeout: int | None = None) -> None:
        """初始化列表缓存。

        Args:
            key: Redis 缓存键。
            max_size: 列表最大长度，超出时自动裁剪。
            timeout: 缓存超时时间（秒）。
        """
        super().__init__(key)
        self.max_size = max_size
        self.timeout = timeout

    def auto_ltrim(self) -> None:
        """当列表长度超过最大值时自动裁剪保留最新元素。"""
        stop = self.connect.llen(self.key)
        if self.max_size < stop:
            start = stop - self.max_size
            self.connect.ltrim(self.key, start, stop)

    def push(self, json_data: Any, *args: Any) -> None:
        """向列表头部推送数据。

        Args:
            json_data: 待推送的数据，自动序列化为 JSON。
            *args: 额外待推送的数据。
        """
        self.connect.lpush(self.key, json.dumps(json_data), *[json.dumps(x) for x in args])
        self.auto_ltrim()
        if self.timeout is not None:
            self.connect.expire(self.key, self.timeout)

    def pop(self) -> Any:
        """从列表尾部弹出数据。

        Returns:
            反序列化后的数据，无数据或异常时返回 None。
        """
        try:
            b_data = self.connect.rpop(self.key)
            if b_data:
                return json.loads(b_data)
        except Exception as e:
            logger.warning(f'{self.key} pop failed {e}')

    def delete(self) -> None:
        """删除列表键。"""
        self.connect.delete(self.key)

    def len(self) -> int:
        """获取列表长度。

        Returns:
            列表元素数量。
        """
        return self.connect.llen(self.key)

    def get_all(self) -> list:
        """获取列表全部元素。

        Returns:
            反序列化后的元素列表。
        """
        return [format_return(k) for k in self.connect.lrange(self.key, 0, -1)]


class CacheSet(CacheRedis):
    """Redis 集合缓存封装。"""

    def __init__(self, key: str) -> None:
        """初始化集合缓存。

        Args:
            key: Redis 缓存键。
        """
        super().__init__(key)

    def get_all(self) -> set:
        """获取集合全部成员。

        Returns:
            反序列化后的成员集合。
        """
        return {format_return(k) for k in self.connect.smembers(self.key)}

    def exist(self, val: Any) -> bool:
        """判断值是否存在于集合中。

        Args:
            val: 待检测的值。

        Returns:
            存在返回 True，否则返回 False。
        """
        return self.connect.sismember(self.key, val)

    def count(self) -> int:
        """获取集合成员数量。

        Returns:
            集合成员数。
        """
        return format_return(self.connect.scard(self.key))

    def push(self, val: Any, *args: Any) -> int:
        """向集合添加成员。

        Args:
            val: 待添加的值。
            *args: 额外待添加的值。

        Returns:
            新增成员数。
        """
        return self.connect.sadd(self.key, format_input(val), *[format_input(x) for x in args])

    def pop(self, val: Any) -> int | None:
        """从集合中移除指定成员。

        Args:
            val: 待移除的值。

        Returns:
            移除的成员数，异常时返回 None。
        """
        try:
            return self.connect.srem(self.key, format_input(val))
        except Exception as e:
            logger.warning(f'{self.key} pop {val} failed {e}')

    def delete(self) -> None:
        """删除集合键。"""
        self.connect.delete(self.key)


class CacheSortedSet(CacheRedis):
    """Redis 有序集合缓存封装。"""

    def __init__(self, key: str) -> None:
        """初始化有序集合缓存。

        Args:
            key: Redis 缓存键。
        """
        super().__init__(key)

    def get_all(self, with_scores: bool = False) -> list:
        """获取有序集合全部成员。

        Args:
            with_scores: 是否包含分数。

        Returns:
            成员列表，包含分数时每项为成员到分数的映射字典。
        """
        return self.get_members(0, -1, with_scores)

    def get_members(self, start: int = 0, end: int = -1, with_scores: bool = False) -> list:
        """获取有序集合指定范围的成员。

        Args:
            start: 起始索引。
            end: 结束索引。
            with_scores: 是否包含分数。

        Returns:
            成员列表。
        """
        data = self.connect.zrevrange(self.key, start, end, with_scores)
        if with_scores:
            return [{format_return(k[0]): format_return(k[1])} for k in data]
        else:
            return [format_return(k) for k in data]

    def exist(self, val: Any) -> bool:
        """判断值是否存在于有序集合中。

        Args:
            val: 待检测的值。

        Returns:
            存在返回 True，否则返回 False。
        """
        return bool(self.connect.zrank(self.key, val))

    def count(self) -> int:
        """获取有序集合成员数量。

        Returns:
            成员数。
        """
        return format_return(self.connect.zcard(self.key))

    def push(self, val: Any, *args: Any) -> int:
        """向有序集合添加成员。

        Args:
            val: 待添加的值或成员到分数的映射。
            *args: 额外待添加的值或映射。

        Returns:
            新增成员数。
        """
        map_data: dict[str, str] = {}
        if isinstance(val, dict):
            map_data.update(val)
        else:
            map_data[format_input(val)] = format_input(time.time())

        for x in args:
            if isinstance(x, dict):
                map_data.update(x)
            else:
                map_data[format_input(x)] = format_input(time.time())

        return self.connect.zadd(self.key, map_data)

    def pop(self, val: Any) -> int | None:
        """从有序集合中移除指定成员。

        Args:
            val: 待移除的值。

        Returns:
            移除的成员数，异常时返回 None。
        """
        try:
            return self.connect.zrem(self.key, format_input(val))
        except Exception as e:
            logger.warning(f'{self.key} pop {val} failed {e}')

    def delete(self) -> None:
        """删除有序集合键。"""
        self.connect.delete(self.key)


class CacheHash(CacheRedis):
    """Redis 哈希缓存封装。"""

    def __init__(self, key: str) -> None:
        """初始化哈希缓存。

        Args:
            key: Redis 缓存键。
        """
        super().__init__(key)

    def get_all(self) -> dict:
        """获取哈希全部字段与值。

        Returns:
            字段到值的映射字典。
        """
        data = {}
        for k, v in self.connect.hgetall(self.key).items():
            data[format_return(k)] = format_return(v)
        return data

    def get(self, key: str) -> Any:
        """获取哈希指定字段的值。

        Args:
            key: 字段名。

        Returns:
            字段值。
        """
        return format_return(self.connect.hget(self.key, key))

    def count(self) -> int:
        """获取哈希字段数量。

        Returns:
            字段数。
        """
        return format_return(self.connect.hlen(self.key))

    def push(self, key: str, val: Any) -> int:
        """设置哈希字段值。

        Args:
            key: 字段名。
            val: 字段值。

        Returns:
            新增字段数。
        """
        return self.connect.hset(self.key, key, format_input(val))

    def pop(self, val: Any) -> int | None:
        """从哈希中移除指定字段。

        Args:
            val: 字段名。

        Returns:
            移除的字段数，异常时返回 None。
        """
        try:
            return self.connect.hdel(self.key, val)
        except Exception as e:
            logger.warning(f'{self.key} pop {val} failed {e}')

    def delete(self) -> None:
        """删除哈希键。"""
        self.connect.delete(self.key)


redis_connect = get_redis_connection('default')
