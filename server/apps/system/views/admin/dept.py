#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : dept
# author : ly_13
# date : 6/16/2023
from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.pagination import DynamicPageNumber
from apps.common.utils import get_logger
from apps.system.models import DeptInfo
from apps.system.serializers.department import DeptSerializer
from apps.system.utils.modelset import ChangeRolePermissionAction

logger = get_logger(__name__)


class DeptFilter(BaseFilterSet):
    pk = filters.UUIDFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = DeptInfo
        fields = ['pk', 'is_active', 'code', 'mode_type', 'auto_bind', 'name', 'description']


class DeptViewSet(BaseModelSet, ChangeRolePermissionAction, ImportExportDataAction):
    """部门"""
    queryset = DeptInfo.objects.all()
    serializer_class = DeptSerializer
    pagination_class = DynamicPageNumber(1000)
    ordering_fields = ['created_time', 'rank']
    filterset_class = DeptFilter
