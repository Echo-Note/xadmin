#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : field
# author : ly_13
# date : 8/10/2024

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import ModelLabelField

logger = get_logger(__name__)


class ModelLabelFieldSerializer(BaseModelSerializer):
    class Meta:
        model = ModelLabelField
        fields = ['pk', 'name', 'label', 'parent', 'field_type', 'created_time', 'updated_time']
        read_only_fields = [x.name for x in ModelLabelField._meta.fields]
        extra_kwargs = {'parent': {'attrs': ['pk', 'name', 'label'], 'read_only': True, 'format': '{label}({pk})'}}


class ModelLabelFieldImportSerializer(BaseModelSerializer):
    class Meta:
        model = ModelLabelField
        fields = ['pk', 'name', 'label', 'parent', 'field_type', 'created_time', 'updated_time']
