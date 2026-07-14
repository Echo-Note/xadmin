#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : serializers
# author : ly_13
# date : 9/14/2024
"""common 应用序列化器。"""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.common.models import Monitor


class MonitorSerializer(serializers.ModelSerializer):
    """服务器监控数据序列化器。"""

    class Meta:
        """序列化器元数据配置。"""

        model = Monitor
        fields = ['cpu_load', 'cpu_percent', 'memory_used', 'disk_used', 'boot_time', 'created_time']
        extra_kwargs = {
            "cpu_load": {'default': 0, 'label': _('CPU Load'), 'help_text': _('CPU load average')},
            "cpu_percent": {'default': 0, 'label': _('CPU Percent'), 'help_text': _('CPU usage percentage')},
            "memory_used": {'default': 0, 'label': _('Memory Used'), 'help_text': _('Used memory amount')},
            "disk_used": {'default': 0, 'label': _('Disk Used'), 'help_text': _('Used disk amount')},
            "boot_time": {'default': 0, 'label': _('Boot Time'), 'help_text': _('System boot time')},
            "created_time": {'label': _('Created time'), 'help_text': _('Record creation time')},
        }
