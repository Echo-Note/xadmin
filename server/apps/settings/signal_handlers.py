#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : signal_handlers.py
# author : ly_13
# date : 7/31/2024
"""设置应用信号处理器，处理设置变更后的缓存刷新与订阅。"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.functional import LazyObject

from apps.common.signals import django_ready
from apps.common.utils import get_logger
from apps.common.utils.connection import RedisPubSub
from apps.settings.models import Setting

logger = get_logger(__name__)


class SettingSubPub(LazyObject):
    """设置变更的 Redis 发布订阅封装。"""

    def _setup(self) -> None:
        """初始化 Redis 发布订阅频道。"""
        self._wrapped = RedisPubSub('settings')


setting_pub_sub = SettingSubPub()


@receiver(post_save, sender=Setting)
def refresh_settings_on_changed(sender: type[Setting], instance: Setting = None, **kwargs) -> None:
    """设置保存后发布变更通知。"""
    if not instance:
        return
    setting_pub_sub.publish((instance.name, instance.cleaned_value))


@receiver(django_ready)
def on_django_ready_add_db_config(sender: object, **kwargs) -> None:
    """Django 就绪后将数据库中的设置加载到 settings。"""
    Setting.refresh_all_settings()


@receiver(django_ready)
def subscribe_settings_change(sender: object, **kwargs) -> None:
    """订阅设置变更，收到变更后刷新对应设置项。"""
    logger.debug("Start subscribe setting change")

    setting_pub_sub.subscribe(lambda name: Setting.refresh_item(name))
