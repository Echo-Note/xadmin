#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : settings
# author : ly_13
# date : 10/25/2024
"""系统设置序列化器定义。"""

from apps.common.core.serializers import BaseModelSerializer
from apps.settings.models import Setting


class SettingSerializer(BaseModelSerializer):
    """系统设置序列化器。"""

    class Meta:
        """元数据配置。"""

        model = Setting
        fields = ['pk', 'name', 'value', 'category', 'is_active', 'encrypted', 'created_time']
        read_only_fields = ['pk']
