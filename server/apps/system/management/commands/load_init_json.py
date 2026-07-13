#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : load_init_json
# author : ly_13
# date : 12/25/2023
import os.path

from django.conf import settings
from django.core.management.commands.loaddata import Command as LoadCommand
from django.db import DEFAULT_DB_ALIAS
from django.db.models.signals import ModelSignal

from settings.models import Setting
from system.models import *


class Command(LoadCommand):
    help = 'load init json data'
    model_names = [MenuMeta, Menu, SystemConfig, DataPermission, UserRole, FieldPermission, ModelLabelField, DeptInfo,
                   Setting]
    missing_args_message = None

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        ModelSignal.send = lambda *args, **kwargs: []  # 忽略任何信号

        # 加载 fixture 前检查是否已有用户，没有则自动创建默认管理员
        # fixture 中 creator_id=1 引用首个用户，必须确保该用户存在
        if not UserInfo.objects.exists():
            _ = UserInfo.objects.create_superuser('xadmin', 'xadmin@dvcloud.xin', 'xAdminPwd!')
            self.stdout.write(self.style.WARNING(
                'Created default admin user (username: xadmin, password: xAdminPwd!), please change it immediately.'))

        fixture_labels = []
        file_root = os.path.join(settings.PROJECT_DIR, "loadjson")
        for model in self.model_names:
            fixture_labels.append(os.path.join(file_root, f"{model._meta.model_name}.json"))
        options["ignore"] = ""
        options["database"] = DEFAULT_DB_ALIAS
        options["app_label"] = ""
        options["exclude"] = []
        options["format"] = "json"
        super(Command, self).handle(*fixture_labels, **options)
