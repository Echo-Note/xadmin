"""模型字段标签管理视图。"""

from django.apps import apps
from django_filters import rest_framework as filters
from drf_spectacular.plumbing import build_object_type, build_basic_type, build_array_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.db.models import QuerySet

from apps.common.base.utils import get_choices_dict
from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import ListDeleteModelSet, ImportExportDataAction
from apps.common.core.pagination import DynamicPageNumber
from apps.common.core.response import ApiResponse
from apps.common.swagger.utils import get_default_response_schema
from apps.common.utils import get_logger
from apps.system.models import ModelLabelField
from apps.system.serializers.field import ModelLabelFieldSerializer, ModelLabelFieldImportSerializer
from apps.system.utils.modelfield import sync_model_field, get_field_lookup_info

logger = get_logger(__name__)


class ModelLabelFieldFilter(BaseFilterSet):
    """模型字段标签过滤器。"""

    pk = filters.UUIDFilter(field_name='id')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    label = filters.CharFilter(field_name='label', lookup_expr='icontains')
    parent = filters.CharFilter(field_name='parent', method='get_parent')

    def get_parent(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """根据 parent 值过滤查询集。

        Args:
            queryset: 原始查询集。
            name: 过滤字段名。
            value: 过滤值。

        Returns:
            过滤后的查询集。
        """
        if value == '0':
            return queryset.filter(parent=None)
        return queryset.filter(parent__id=value)

    class Meta:
        """过滤器元数据。"""

        model = ModelLabelField
        fields = ['pk', 'name', 'label', 'parent', 'field_type', 'created_time']


class ModelLabelFieldViewSet(ListDeleteModelSet, ImportExportDataAction):
    """模型字段标签视图集。"""

    queryset = ModelLabelField.objects.all()
    serializer_class = ModelLabelFieldSerializer
    pagination_class = DynamicPageNumber(1000)
    import_data_serializer_class = ModelLabelFieldImportSerializer
    ordering_fields = ['created_time', 'updated_time']
    filterset_class = ModelLabelFieldFilter

    @extend_schema(
        responses=get_default_response_schema(
            {
                'choices_dict': build_object_type(
                    properties={
                        'key': build_array_type(
                            build_object_type(
                                properties={
                                    'value': build_basic_type(OpenApiTypes.STR),
                                    'label': build_basic_type(OpenApiTypes.STR),
                                }
                            )
                        )
                    }
                )
            }
        )
    )
    @action(methods=['get'], detail=False, url_path='choices')
    def choices_dict(self, request: Request, *args, **kwargs) -> Response:
        """获取字段类型的选项字典。"""
        disabled_choices = [
            ModelLabelField.KeyChoices.TEXT,
            ModelLabelField.KeyChoices.JSON,
            ModelLabelField.KeyChoices.DATE,
            ModelLabelField.KeyChoices.DEPARTMENTS
        ]
        result = get_choices_dict(ModelLabelField.KeyChoices.choices, disabled_choices=disabled_choices)
        return ApiResponse(choices_dict={'choices': result})

    @extend_schema(
        parameters=[
            OpenApiParameter(name='table', required=True, type=str),
            OpenApiParameter(name='field', required=True, type=str),
        ],
        responses=get_default_response_schema({'data': build_array_type(build_basic_type(OpenApiTypes.STR))})
    )
    @action(methods=['get'], detail=False, queryset=ModelLabelField.objects, filterset_class=None)
    def lookups(self, request: Request, *args, **kwargs) -> Response:
        """获取指定模型字段的查询操作符列表。"""
        table = request.query_params.get('table')
        field = request.query_params.get('field')
        if table and field:
            if table == '*':
                table = 'system.userinfo'
            obj = self.filter_queryset(self.get_queryset()).filter(name=field, parent__name=table,
                                                                   parent__parent=None).first()
            if obj:
                mt = apps.get_model(table)
                if mt:
                    mf = mt._meta.get_field(field)
                    if mf:
                        return ApiResponse(data=get_field_lookup_info(mf.get_class_lookups().keys()))
        return ApiResponse(code=1001)

    @extend_schema(responses=get_default_response_schema())
    @action(methods=['get'], detail=False)
    def sync(self, request: Request, *args, **kwargs) -> Response:
        """同步所有模型的字段标签。"""
        sync_model_field()
        return ApiResponse()
