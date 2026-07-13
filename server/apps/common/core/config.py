#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : config
# author : ly_13
# date : 12/15/2023
# 修改下面配置之后，记得清理一下redis缓存： python manage.py expire_caches 'config_*'
"""系统配置缓存模块，提供配置的数据库读取、缓存管理及模板渲染功能。"""


import json
import re
from typing import Any

from django.template import Context, Template, TemplateSyntaxError
from django.template.base import VariableNode
from rest_framework import serializers

from apps.common.cache.storage import UserSystemConfigCache
from apps.common.utils import get_logger
from server import settings
from apps.system.models import SystemConfig, UserPersonalConfig

logger = get_logger(__name__)


class SystemConfigSerializer(serializers.ModelSerializer):
    """系统配置序列化器。"""

    class Meta:
        """元数据配置。"""

        model = SystemConfig
        fields = "__all__"


def get_render_context(tmp: str, context: dict) -> str:
    """渲染模板字符串，将大写变量名自动替换为系统配置值。

    Args:
        tmp: 模板字符串。
        context: 渲染上下文字典。

    Returns:
        渲染后的字符串。
    """
    template = Template(tmp)
    for node in template.nodelist:
        if isinstance(node, VariableNode):
            v_key = re.findall(r'<Variable Node: (.*)>', str(node))
            if v_key and v_key[0].isupper():
                context[v_key[0]] = getattr(SysConfig, v_key[0])
    context = Context(context)
    return template.render(context)


class ConfigCacheBase(object):
    """配置缓存基类，提供配置的数据库读写、缓存管理及模板渲染。"""

    def __init__(self, px: str = 'system', model: Any = SystemConfig, cache: Any = UserSystemConfigCache,
                 serializer: Any = SystemConfigSerializer, timeout: int = 60 * 60 * 24 * 30,
                 filter_kwargs: dict | None = None) -> None:
        """初始化配置缓存基类。

        Args:
            px: 缓存键前缀。
            model: 配置对应的 Django 模型类。
            cache: 缓存类。
            serializer: 序列化器类。
            timeout: 缓存超时时间（秒）。
            filter_kwargs: 查询过滤条件。
        """
        if filter_kwargs is None:
            filter_kwargs = {}
        self.px = px
        self.model = model
        self.cache = cache
        self.timeout = timeout
        self.serializer = serializer
        self.filter_kwargs = filter_kwargs

    def invalid_config_cache(self, key: str = '*') -> None:
        """使指定键的缓存失效。

        Args:
            key: 配置键名，默认 '*' 表示全部。
        """
        UserSystemConfigCache(f'{self.px}_{key}').del_many()

    def get_render_value(self, value: str) -> dict:
        """渲染配置值，支持模板语法和变量引用。

        Args:
            value: 待渲染的配置值字符串。

        Returns:
            渲染并解析后的配置值。
        """
        if value:
            try:
                context_dict = {}
                for sys_obj_dict in self.model.objects.filter(is_active=True).values().all():
                    str_value = json.dumps(sys_obj_dict['value'])  # 将dict转换为json字符串进行匹配
                    if re.findall('{{.*%s.*}}' % sys_obj_dict['key'], str_value):
                        logger.warning(f"get same render key. so continue")
                        continue
                    context_dict[sys_obj_dict['key']] = str_value
                try:
                    value = get_render_context(value, context_dict)
                except TemplateSyntaxError as e:
                    res_list = re.findall("Could not parse the remainder: '{{(.*?)}}'", str(e))
                    for res in res_list:
                        r_value = self.get_render_value(f'{{{{{res}}}}}')
                        value = value.replace(f'{{{{{res}}}}}', f'{r_value}')
                    value = self.get_render_value(value)
                except Exception as e:
                    logger.warning(f"db config - render failed {e}")
            except Exception as e:
                logger.warning(f"db config - render failed {e}")
        value = value.replace('"(', '').replace(')"', '')  # 支持"({{ h }})"， 为了转换变量，h不能为字符串
        try:
            value = json.loads(value)
        except Exception as e:
            logger.warning(f"db config - json loads failed {e}")
        # if isinstance(value, str):
        #     if value.isdigit():
        #         return int(value)
        #     v_group = re.findall('"(.*?)"', value)
        #     if v_group and len(v_group) == 1 and v_group[0].isdigit():
        #         return int(v_group[0])
        return value

    def get_value_from_db(self, key: str) -> dict:
        """取得数据是激活的数据，如果数据未激活，则取默认数据

        Args:
            key: 配置键名。

        Returns:
            数据库中该配置的序列化数据字典。
        """
        data = self.serializer(self.model.objects.filter(is_active=True, key=key, **self.filter_kwargs).first()).data
        if re.findall('{{.*%s.*}}' % data['key'], json.dumps(data['value'])):  # 防止渲染出现递归
            logger.warning(f"get same render key:{key}. so get default value")
            data['key'] = ''
        return data

    def get_default_data(self, key: str, default_data: Any) -> Any:
        """获取配置的默认数据。

        Args:
            key: 配置键名。
            default_data: 默认数据，为 None 时返回空字典。

        Returns:
            默认数据。
        """
        if default_data is None:
            default_data = {}
        return default_data

    def get_value(self, key: str, default_data: Any = None, ignore_access: bool = True) -> Any:
        """获取配置值。

        Args:
            key: 配置键名。
            default_data: 默认数据。
            ignore_access: 是否忽略访问权限。

        Returns:
            配置值，不存在时返回 None。
        """
        data = self.get_data(key, default_data, ignore_access)
        if data:
            return data.get('value')
        return data

    def get_data(self, key: str, default_data: Any = None, ignore_access: bool = True) -> dict:
        """获取配置的完整数据，优先读缓存，缓存未命中时读数据库。

        Args:
            key: 配置键名。
            default_data: 默认数据。
            ignore_access: 是否忽略访问权限。

        Returns:
            配置数据字典，无权限时返回空字典。
        """
        cache = self.cache(f'{self.px}_{key}')
        cache_data = cache.get_storage_cache()
        if cache_data is not None and cache_data.get('key', '') == key:
            if ignore_access or cache_data.get('access'):
                return cache_data
        db_data = self.get_value_from_db(key)
        d_key = db_data.get('key', '')
        if d_key != key:
            data = self.get_default_data(key, default_data)
            if data is not None:
                db_data['value'] = data
                db_data['key'] = key
                db_data['access'] = True
        db_data['value'] = self.get_render_value(json.dumps(db_data['value']))
        cache.set_storage_cache(db_data, timeout=self.timeout)
        if ignore_access or db_data.get('access'):
            return db_data
        return {}

    def save_db(self, key: str, value: Any, is_active: bool | None, description: str | None,
                **kwargs: Any) -> tuple:
        """保存配置到数据库。

        Args:
            key: 配置键名。
            value: 配置值。
            is_active: 是否激活，None 表示不更新。
            description: 描述信息，None 表示不更新。
            **kwargs: 透传给 update_or_create 的扩展参数。

        Returns:
            update_or_create 返回的 (实例, 是否创建) 元组。
        """
        defaults = {'value': value}
        if is_active is not None:
            defaults['is_active'] = is_active
        if description is not None:
            defaults['description'] = description
        return self.model.objects.update_or_create(key=key, defaults=defaults, **kwargs)

    def delete_db(self, key: str, **kwargs: Any) -> tuple:
        """从数据库删除指定配置。

        Args:
            key: 配置键名。
            **kwargs: 透传给 filter 的扩展参数。

        Returns:
            delete 返回的 (删除数量, 类型计数字典) 元组。
        """
        return self.model.objects.filter(key=key, **kwargs).delete()

    def set_value(self, key: str, value: Any, is_active: bool | None = None, description: str | None = None,
                  **kwargs: Any) -> tuple:
        """设置配置值并刷新缓存。

        Args:
            key: 配置键名。
            value: 配置值。
            is_active: 是否激活。
            description: 描述信息。
            **kwargs: 透传给 save_db 的扩展参数。

        Returns:
            save_db 返回的 (实例, 是否创建) 元组。
        """
        obj = self.save_db(key, value, is_active, description, **kwargs)
        self.cache(f'{self.px}_{key}').del_storage_cache()
        return obj

    def set_default_value(self, key: str, **kwargs: Any) -> tuple:
        """将配置重置为当前值的默认值并保存。

        Args:
            key: 配置键名。
            **kwargs: 透传给 set_value 的扩展参数。

        Returns:
            set_value 返回的 (实例, 是否创建) 元组。
        """
        return self.set_value(key, self.get_value(key, None), **kwargs)

    def del_value(self, key: str, **kwargs: Any) -> None:
        """删除配置值及缓存。

        Args:
            key: 配置键名。
            **kwargs: 透传给 delete_db 的扩展参数。
        """
        self.delete_db(key, **kwargs)
        self.cache(f'{self.px}_{key}').del_storage_cache()

    def __getattribute__(self, name: str) -> Any:
        """重写属性访问，未定义的属性名自动作为配置键查询。

        Args:
            name: 属性名。

        Returns:
            属性值或对应配置的值。
        """
        if name == 'shape':
            return ''
        try:
            return object.__getattribute__(self, name)
        except Exception as e:
            logger.error(f"__getattribute__ Error  {e}  {name}")
            return self.get_value(name)


class BaseConfCache(ConfigCacheBase):
    """基础配置缓存，提供文件/图片上传大小等配置。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化基础配置缓存。

        Args:
            *args: 透传给父类的位置参数。
            **kwargs: 透传给父类的关键字参数。
        """
        super(BaseConfCache, self).__init__(*args, **kwargs)

    @property
    def FILE_UPLOAD_SIZE(self) -> Any:
        """文件上传大小限制配置。"""
        return self.get_value('FILE_UPLOAD_SIZE', settings.FILE_UPLOAD_SIZE)

    @property
    def PICTURE_UPLOAD_SIZE(self) -> Any:
        """图片上传大小限制配置。"""
        return self.get_value('PICTURE_UPLOAD_SIZE', settings.PICTURE_UPLOAD_SIZE)


class MessagePushConfCache(ConfigCacheBase):
    """消息推送配置缓存，提供消息通知和聊天消息推送开关。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化消息推送配置缓存。

        Args:
            *args: 透传给父类的位置参数。
            **kwargs: 透传给父类的关键字参数。
        """
        super(MessagePushConfCache, self).__init__(*args, **kwargs)

    @property
    def PUSH_MESSAGE_NOTICE(self) -> Any:
        """消息通知推送开关。"""
        return self.get_value('PUSH_MESSAGE_NOTICE', True)

    @property
    def PUSH_CHAT_MESSAGE(self) -> Any:
        """聊天消息推送开关。"""
        return self.get_value('PUSH_CHAT_MESSAGE', True)


class ConfigCache(BaseConfCache, MessagePushConfCache):
    """系统配置缓存，继承基础配置和消息推送配置。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化系统配置缓存。

        Args:
            *args: 透传给父类的位置参数。
            **kwargs: 透传给父类的关键字参数。
        """
        super(ConfigCache, self).__init__(*args, **kwargs)


SysConfig = ConfigCache()


class UserConfigSerializer(serializers.ModelSerializer):
    """用户个人配置序列化器。"""

    class Meta:
        """元数据配置。"""

        model = UserPersonalConfig
        fields = "__all__"


class UserPersonalConfigCache(ConfigCache):
    """用户个人配置缓存，按用户隔离配置数据。"""

    def __init__(self, user_obj: Any) -> None:
        """初始化用户个人配置缓存。

        Args:
            user_obj: 用户对象或用户主键。
        """
        self.user_obj = user_obj
        self.filter_kwargs = {'owner': self.user_obj}
        if isinstance(user_obj, (str, int)):
            key = user_obj
            self.filter_kwargs = {'owner_id': self.user_obj}
        else:
            key = user_obj.pk
        super().__init__(f'user_{key}', UserPersonalConfig, UserSystemConfigCache, UserConfigSerializer,
                         filter_kwargs=self.filter_kwargs)

    def get_default_data(self, key: str, default_data: Any) -> Any:
        """获取用户个人配置的默认数据，支持从系统配置继承。

        Args:
            key: 配置键名。
            default_data: 默认数据。

        Returns:
            默认数据，若系统配置允许继承则返回继承值，否则返回空字典。
        """
        data = SysConfig.get_data(key, default_data)
        if data and data.get('inherit'):
            return data.get('value')
        return {}

    def delete_db(self, key: str, **kwargs: Any) -> tuple:
        """从数据库删除用户个人配置。

        Args:
            key: 配置键名。
            **kwargs: 透传给父类的扩展参数。

        Returns:
            delete 返回的 (删除数量, 类型计数字典) 元组。
        """
        return super(UserPersonalConfigCache, self).delete_db(key, **self.filter_kwargs)

    def save_db(self, key: str, value: Any, is_active: bool | None = None, description: str | None = None,
                **kwargs: Any) -> tuple:
        """保存用户个人配置到数据库。

        Args:
            key: 配置键名。
            value: 配置值。
            is_active: 是否激活。
            description: 描述信息。
            **kwargs: 透传给父类的扩展参数。

        Returns:
            save_db 返回的 (实例, 是否创建) 元组。
        """
        return super(UserPersonalConfigCache, self).save_db(key, value, is_active, description, **self.filter_kwargs,
                                                            **kwargs)

    def set_default_value(self, key: str, **kwargs: Any) -> tuple:
        """将用户个人配置重置为默认值并保存。

        Args:
            key: 配置键名。
            **kwargs: 透传给父类的扩展参数。

        Returns:
            set_default_value 返回的 (实例, 是否创建) 元组。
        """
        return super(UserPersonalConfigCache, self).set_default_value(key, **self.filter_kwargs)


UserConfig = UserPersonalConfigCache
