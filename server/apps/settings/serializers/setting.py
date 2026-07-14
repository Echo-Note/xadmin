#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : settings
# author : ly_13
# date : 10/25/2024
"""系统设置序列化器定义。"""

from django.utils.translation import gettext_lazy as _

from apps.common.core.serializers import BaseModelSerializer
from apps.settings.models import Setting


class SettingSerializer(BaseModelSerializer):
    """系统设置序列化器。"""

    class Meta:
        """元数据配置。"""

        model = Setting
        fields = ['pk', 'name', 'value', 'category', 'is_active', 'encrypted', 'created_time']
        read_only_fields = ['pk']
        extra_kwargs = {
            'pk': {'label': _('ID'), 'help_text': _('Unique identifier of the setting item')},
            'name': {'label': _('Name'), 'help_text': _('Name of the setting item')},
            'value': {'label': _('Value'), 'help_text': _('Value of the setting item (may be encrypted)')},
            'category': {'label': _('Category'), 'help_text': _('Category to which the setting item belongs')},
            'is_active': {'label': _('Is active'), 'help_text': _('Whether the setting item is enabled')},
            'encrypted': {'label': _('Encrypted'), 'help_text': _('Whether the setting value is stored encrypted')},
            'created_time': {'label': _('Created time'), 'help_text': _('Time when the setting item was created')},
        }
