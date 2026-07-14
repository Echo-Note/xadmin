#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : models
# author : ly_13
# date : 9/14/2024
"""common 应用数据模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Monitor(models.Model):
    """服务器性能监控记录模型。"""

    cpu_load = models.FloatField(verbose_name=_("CPU Load"), default=0, help_text=_("System CPU load average (1-minute)"), db_comment="CPU负载")
    cpu_percent = models.FloatField(verbose_name=_("CPU Percent"), default=0, help_text=_("Overall CPU utilization percentage"), db_comment="CPU使用率")
    memory_used = models.FloatField(verbose_name=_("Memory Used"), help_text=_("Amount of physical memory currently in use (bytes)"), db_comment="已用内存")
    disk_used = models.FloatField(verbose_name=_("Disk Used"), default=0, help_text=_("Amount of disk space currently in use (bytes)"), db_comment="已用磁盘")
    boot_time = models.FloatField(verbose_name=_("Boot Time"), default=0, help_text=_("System boot timestamp (Unix epoch seconds)"), db_comment="系统启动时间")
    created_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Created time"), help_text=_("Timestamp when this monitoring record was collected"), db_comment="记录创建时间")

    class Meta:
        """模型元数据配置。"""

        verbose_name = _("Monitor")
        verbose_name_plural = verbose_name
        db_table_comment = "服务器性能监控记录表"

    def __str__(self) -> str:
        """返回监控记录的可读描述。"""
        return "%s-%s" % (self.created_time, self.cpu_load)
