#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : server
# filename : role
# author : ly_13
# date : 6/19/2023

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.utils import get_logger
from apps.system.models import UserRole
from apps.system.serializers.role import RoleSerializer, ListRoleSerializer

logger = get_logger(__name__)


class RoleFilter(BaseFilterSet):
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    code = filters.CharFilter(field_name='code', lookup_expr='icontains')

    class Meta:
        model = UserRole
        fields = ['name', 'code', 'is_active', 'description']


class RoleViewSet(BaseModelSet, ImportExportDataAction):
    """角色"""
    queryset = UserRole.objects.all()
    serializer_class = RoleSerializer
    list_serializer_class = ListRoleSerializer
    ordering_fields = ['updated_time', 'name', 'created_time']
    filterset_class = RoleFilter
