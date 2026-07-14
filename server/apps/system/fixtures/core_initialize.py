# -*- coding: utf-8 -*-

"""
初始化基类。

提供通用的 JSON fixture 加载与序列化器保存流程，
供各应用的 initialize.py 继承使用。

用法：继承此类，重写 run() 方法，在其中调用 init_base()。
"""

import json
import os

from django.apps import apps


class CoreInitialize:
    """初始化基类。

    属性：
        app: 应用名称（用于定位 fixtures 目录）。
        reset: 是否重置已有数据。
        creator_id: 创建者用户 ID。
    """

    creator_id = None
    reset = False

    def __init__(self, reset: bool = False, creator_id: int = None, app: str = '') -> None:
        """初始化基类。

        Args:
            reset: 是否重置已有数据。
            creator_id: 创建者用户 ID，为空则取首个用户。
            app: 应用名称。
        """
        self.reset = reset or self.reset
        self.creator_id = creator_id or self.creator_id
        self.app = app or ''

    def init_base(self, serializer_class: type, unique_fields: list[str] = None) -> None:
        """通用的 fixture 加载与序列化器保存方法。

        从 {app}/fixtures/init_{model_name}.json 读取数据，
        通过 unique_fields 查找已存在记录实现幂等，
        使用 serializer_class 进行反序列化与保存。

        Args:
            serializer_class: 初始化序列化器类。
            unique_fields: 用于查找已有记录的唯一字段列表。
        """
        model = serializer_class.Meta.model
        model_name = model._meta.model_name
        app_path = apps.get_app_config(self.app.split('.')[-1]).path
        path_file = os.path.join(app_path, 'fixtures', f'init_{model_name}.json')

        if not os.path.isfile(path_file):
            print(f"[{self.app}] 文件 {path_file} 不存在，跳过初始化")
            return

        with open(path_file, encoding='utf-8') as f:
            data_list = json.load(f)

        for data in data_list:
            # 构建过滤条件查找已有记录
            filter_data = {}
            if unique_fields:
                for field in unique_fields:
                    if field in data:
                        filter_data[field] = data[field]
            else:
                for key, value in data.items():
                    if isinstance(value, list) or value is None or value == '':
                        continue
                    filter_data[key] = value

            instance = model.objects.filter(**filter_data).first()
            data['reset'] = self.reset
            serializer = serializer_class(instance=instance, data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        print(f"[{self.app}][{model_name}] 初始化完成")

    def run(self) -> None:
        """执行初始化入口，子类必须重写。"""
        raise NotImplementedError('.run() must be overridden')
