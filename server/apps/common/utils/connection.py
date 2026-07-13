"""Redis 发布订阅与数据库连接工具模块。"""

import json
import threading
import time
from collections.abc import Callable
from typing import Any

import redis
from django.core.cache import cache
from redis.client import PubSub

from apps.common.core.db.utils import safe_db_connection
from apps.common.utils import get_logger

logger = get_logger(__name__)


def get_redis_client(db: int = 0) -> redis.Redis:
    """获取 Redis 客户端实例。

    Args:
        db: Redis 数据库编号。

    Returns:
        Redis 客户端实例。
    """
    client = cache.client.get_client()
    assert isinstance(client, redis.Redis)
    return client


class RedisPubSub:
    """Redis 发布订阅封装类。"""

    def __init__(self, ch: str, db: int = 10) -> None:
        """初始化发布订阅对象。

        Args:
            ch: 频道名称。
            db: Redis 数据库编号。
        """
        self.ch = ch
        self.db = db
        self.redis = get_redis_client(db)

    def subscribe(
        self,
        _next: Callable[[Any], None],
        error: Callable[[dict, Any], None] | None = None,
        complete: Callable[[], None] | None = None,
    ) -> 'Subscription':
        """订阅频道并启动消息处理。

        Args:
            _next: 消息处理回调函数。
            error: 错误处理回调函数。
            complete: 完成回调函数。

        Returns:
            订阅对象。
        """
        ps = self.redis.pubsub()
        ps.subscribe(self.ch)
        sub = Subscription(self, ps)
        sub.keep_handle_msg(_next, error, complete)
        return sub

    def resubscribe(
        self,
        _next: Callable[[Any], None],
        error: Callable[[dict, Any], None] | None = None,
        complete: Callable[[], None] | None = None,
    ) -> None:
        """重新建立 Redis 连接并订阅频道。"""
        self.redis = get_redis_client(self.db)
        self.subscribe(_next, error, complete)

    def publish(self, data: Any) -> bool:
        """向频道发布消息。

        Args:
            data: 待发布的消息数据，将序列化为 JSON。

        Returns:
            发布成功返回 True。
        """
        data_json = json.dumps(data)
        self.redis.publish(self.ch, data_json)
        return True


class Subscription:
    """Redis 订阅封装类，处理消息接收与重试。"""

    def __init__(self, pb: RedisPubSub, sub: PubSub) -> None:
        """初始化订阅对象。

        Args:
            pb: 关联的发布订阅对象。
            sub: Redis PubSub 对象。
        """
        self.pb = pb
        self.ch = pb.ch
        self.sub = sub
        self.unsubscribed = False

    def _handle_msg(
        self,
        _next: Callable[[Any], None],
        error: Callable[[dict, Any], None] | None,
        complete: Callable[[], None] | None,
    ) -> None:
        """处理接收到的消息，依次调用回调函数。

        Args:
            _next: 消息处理回调函数。
            error: 错误处理回调函数。
            complete: 完成回调函数。
        """
        msgs = self.sub.listen()

        if error is None:
            error = lambda m, i: None

        if complete is None:
            complete = lambda: None

        try:
            for msg in msgs:
                if msg['type'] != 'message':
                    continue
                item = None
                try:
                    item_json = msg['data'].decode()
                    item = json.loads(item_json)

                    with safe_db_connection():
                        _next(item)
                except Exception as e:
                    error(msg, item)
                    logger.error('Subscribe handler handle msg error: {}'.format(e))
        except Exception as e:
            if self.unsubscribed:
                logger.debug('Subscription unsubscribed')
            else:
                logger.error('Consume msg error: {}'.format(e))
                self.retry(_next, error, complete)
                return

        try:
            complete()
        except Exception as e:
            logger.error('Complete subscribe error: {}'.format(e))
            pass

        try:
            self.unsubscribe()
        except Exception as e:
            logger.error('Redis observer close error: {}'.format(e))

    def keep_handle_msg(
        self,
        _next: Callable[[Any], None],
        error: Callable[[dict, Any], None] | None,
        complete: Callable[[], None] | None,
    ) -> threading.Thread:
        """在守护线程中持续处理消息。

        Args:
            _next: 消息处理回调函数。
            error: 错误处理回调函数。
            complete: 完成回调函数。

        Returns:
            消息处理线程。
        """
        t = threading.Thread(target=self._handle_msg, args=(_next, error, complete))
        t.daemon = True
        t.start()
        return t

    def unsubscribe(self) -> None:
        """取消订阅并关闭连接。"""
        self.unsubscribed = True
        logger.info('Unsubscribed from channel: {}'.format(self.sub))
        try:
            self.sub.close()
        except Exception as e:
            logger.warning('Unsubscribe msg error: {}'.format(e))

    def retry(
        self,
        _next: Callable[[Any], None],
        error: Callable[[dict, Any], None] | None,
        complete: Callable[[], None] | None,
    ) -> None:
        """重试订阅频道，指数退避等待。

        Args:
            _next: 消息处理回调函数。
            error: 错误处理回调函数。
            complete: 完成回调函数。
        """
        logger.info('Retry subscribe channel: {}'.format(self.ch))
        times = 0

        while True:
            try:
                self.unsubscribe()
                self.pb.resubscribe(_next, error, complete)
                break
            except Exception as e:
                logger.error('Retry #{} {} subscribe channel error: {}'.format(times, self.ch, e))
                times += 1
                time.sleep(times * 2)
