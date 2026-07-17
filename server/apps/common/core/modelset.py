#!/usr/bin/env python
# project : server
# filename : modelset
# author : ly_13
# date : 6/2/2023
"""视图集模块，提供缓存、上传、排序、批量操作及增删改查等通用视图混入。"""

import importlib
import itertools
import json
import math
import uuid
from collections.abc import Callable
from hashlib import md5
from typing import Any

from django.conf import settings
from django.db import models, transaction
from django.forms.widgets import DateTimeInput, SelectMultiple
from django.utils.translation import gettext_lazy as _
from django_filters.utils import get_model_field
from django_filters.widgets import DateRangeWidget
from drf_spectacular.plumbing import build_array_type, build_basic_type, build_object_type
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiRequest, OpenApiResponse, extend_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.fields import CharField
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.utils import encoders
from rest_framework.viewsets import GenericViewSet

from apps.common.base.magic import cache_response
from apps.common.base.utils import get_choices_dict
from apps.common.core.config import SysConfig
from apps.common.core.response import ApiResponse
from apps.common.core.serializers import BasePrimaryKeyRelatedField
from apps.common.core.utils import has_self_fields, topological_sort
from apps.common.drf.renders.csv import CSVFileRenderer
from apps.common.drf.renders.excel import ExcelFileRenderer
from apps.common.swagger.utils import get_default_response_schema
from apps.common.tasks import background_task_view_set_job
from apps.common.utils import get_logger

logger = get_logger(__name__)


def get_upload_input_type_suffix(value: Any, default: str) -> str:
    """判断字段是否为上传文件类型并返回对应后缀。

    Args:
        value: 序列化器字段对象。
        default: 默认输入类型。

    Returns:
        上传文件时返回 ``_file``，否则返回空字符串。
    """
    if hasattr(value, 'child_relation'):
        value = value.child_relation
    try:
        if (
            value.queryset.model._meta.label == 'system.UploadFile'
            and isinstance(value, BasePrimaryKeyRelatedField)
            and default in ['object_related_field', 'm2m_related_field']
        ):
            return '_file'
    except Exception:
        pass
    return ''


def get_format_intput_type(value: Any, default: str = '') -> str:
    """根据字段的 input_type 属性组装前端输入类型字符串。

    Args:
        value: 序列化器字段对象。
        default: 默认输入类型。

    Returns:
        组装后的输入类型字符串，为空时返回 default。
    """
    input_type_prefix = ''
    input_type = default
    input_type_suffix = get_upload_input_type_suffix(value, default)

    if hasattr(value, 'input_type') and value.input_type is not None:
        input_type = value.input_type
    if hasattr(value, 'input_type_prefix') and value.input_type_prefix is not None:
        input_type_prefix = f'{value.input_type_prefix}_' if value.input_type_prefix else ''
    if hasattr(value, 'input_type_suffix') and value.input_type_suffix is not None:
        input_type_suffix = f'_{value.input_type_suffix}' if value.input_type_suffix else ''
    input_type_str = input_type_prefix + input_type + input_type_suffix
    if input_type_str:
        return input_type_str
    return default


def run_view_by_celery_task(
    view: Any, request: Request, kwargs: dict, data: list, batch_length: int = 100
) -> Response | None:
    """通过 Celery 异步执行视图任务，批量提交数据。

    Args:
        view: 视图对象。
        request: DRF 请求对象。
        kwargs: 视图关键字参数。
        data: 待处理的数据列表。
        batch_length: 每批数据量大小。

    Returns:
        异步任务提交成功时返回 ``ApiResponse``，需要同步执行时返回 None。
    """
    task = kwargs.get(
        'task', request.query_params.get('task', 'true').lower() in ['true', '1', 'yes']
    )  # 默认为任务异步导入
    if task:
        view_str = f'{view.__class__.__module__}.{view.__class__.__name__}'
        meta = request.META
        task_id = uuid.uuid4()
        if isinstance(data, dict):
            data = [data]
        meta['task_count'] = math.ceil(len(data) / batch_length)
        meta['action'] = view.action
        try:
            # 检查Celery是否可用，如果不可用则直接执行任务
            from server.celery import app

            inspect = app.control.inspect()
            active_workers = inspect.active()
            if active_workers is None or not active_workers:
                # 没有活跃的worker，直接执行任务
                logger.warning('No active Celery workers found, executing task directly')
                return None  # 返回None表示需要直接执行
            for index, batch in enumerate(itertools.batched(data, batch_length)):
                meta['task_id'] = f'{task_id}_{index}'
                meta['task_index'] = index
                res = background_task_view_set_job.apply_async(
                    args=(view_str, meta, json.dumps(batch), view.action_map), task_id=meta['task_id']
                )
                logger.info(f'add {view_str} task success. {res}')
            return ApiResponse(detail=_('Task add success'))
        except Exception as e:
            logger.error(f'Celery task submission failed: {e}, executing task directly')
            return None  # 如果提交任务失败，也返回None表示需要直接执行
    return None  # 如果task参数为false，直接执行


class CacheDetailResponseMixin:
    """详情视图缓存混入，提供基于用户和视图的缓存键生成及失效。"""

    def get_cache_key(
        self, view_instance: Any, view_method: Callable, request: Request, args: tuple, kwargs: dict
    ) -> str:
        """生成详情视图的缓存键。

        Args:
            view_instance: 视图实例。
            view_method: 视图方法。
            request: DRF 请求对象。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            缓存键字符串。
        """
        func_name = f'{view_instance.__class__.__name__}_{view_method.__name__}'
        return f'{func_name}_{request.user.pk}'

    @classmethod
    def invalid_cache(cls, pk: Any, methods: list | None = None) -> None:
        """使指定主键的缓存失效。

        Args:
            pk: 主键值。
            methods: 需要失效的方法名列表，默认为 ['retrieve', 'get']。
        """
        if methods is None:
            methods = ['retrieve', 'get']
        for method in methods:
            cache_response.invalid_cache(f'{cls.__name__}_{method}_{pk}')


class CacheListResponseMixin:
    """列表视图缓存混入，提供基于用户和查询参数的缓存键生成及失效。"""

    def get_cache_key(
        self, view_instance: Any, view_method: Callable, request: Request, args: tuple, kwargs: dict
    ) -> str:
        """生成列表视图的缓存键，包含查询参数的哈希值。

        Args:
            view_instance: 视图实例。
            view_method: 视图方法。
            request: DRF 请求对象。
            args: 位置参数。
            kwargs: 关键字参数。

        Returns:
            缓存键字符串。
        """
        func_name = f'{view_instance.__class__.__name__}_{view_method.__name__}'
        return f'{func_name}_{request.user.pk}_{md5(json.dumps(request.query_params, sort_keys=True).encode("utf-8")).hexdigest()}'

    @classmethod
    def invalid_cache(cls, pk: Any, methods: list | None = None) -> None:
        """使指定主键的列表缓存失效。

        Args:
            pk: 主键值。
            methods: 需要失效的方法名列表，默认为 ['list']。
        """
        if methods is None:
            methods = ['list']
        for method in methods:
            cache_response.invalid_cache(f'{cls.__name__}_{method}_{pk}')


class UploadFileAction:
    """文件上传视图混入，提供头像/图片上传接口。"""

    FILE_UPLOAD_TYPE = ['png', 'jpeg', 'jpg', 'gif']
    FILE_UPLOAD_FIELD = 'avatar'
    FILE_UPLOAD_SIZE = settings.FILE_UPLOAD_SIZE

    def get_upload_size(self) -> Any:
        """获取图片上传大小限制配置。"""
        return SysConfig.PICTURE_UPLOAD_SIZE

    @extend_schema(
        request=OpenApiRequest(build_object_type(properties={'file': build_basic_type(OpenApiTypes.BINARY)})),
        responses=get_default_response_schema(),
    )
    @action(methods=['post'], detail=True, parser_classes=(MultiPartParser,))
    def upload(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """上传头像"""
        self.FILE_UPLOAD_SIZE = self.get_upload_size()
        files = request.FILES.getlist('file', [])
        instance = self.get_object()
        file_obj = files[0]
        try:
            file_type = file_obj.name.split('.')[-1]
            if file_type not in self.FILE_UPLOAD_TYPE:
                raise
            if file_obj.size > self.FILE_UPLOAD_SIZE:
                return ApiResponse(code=1003, detail=_('Image size cannot exceed {}').format(self.FILE_UPLOAD_SIZE))
        except Exception:
            return ApiResponse(
                code=1002, detail=_('Wrong image type, the type should be {}').format(','.join(self.FILE_UPLOAD_TYPE))
            )
        setattr(instance, self.FILE_UPLOAD_FIELD, file_obj)
        instance.modifier = request.user
        instance.save(update_fields=[self.FILE_UPLOAD_FIELD, 'modifier'])
        return ApiResponse()


class RankAction:
    """排序视图混入，提供批量排序接口。"""

    filter_queryset: Callable
    get_queryset: Callable

    @extend_schema(
        request=OpenApiRequest(build_array_type(build_basic_type(OpenApiTypes.STR))),
        responses=get_default_response_schema(),
    )
    @action(methods=['post'], detail=False, url_path='rank')
    def rank(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """{cls}排序"""
        rank = 1
        for pk in request.data:
            self.filter_queryset(self.get_queryset()).filter(pk=pk).update(rank=rank)
            rank += 1
        return ApiResponse(detail=_('Sorting saved successfully'))


class ChoicesAction:
    """字段选项视图混入，提供获取模型字段 choices 的接口。"""

    choices_models: list

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
    def choices_dict(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """获取{cls}的字段选择"""
        result = {}
        models = getattr(self, 'choices_models', None)
        if not models:
            models = [self.queryset.model]
        for model in models:
            for field in model._meta.fields:
                choices = field.choices
                if choices:
                    result[field.name] = get_choices_dict(choices)
        return ApiResponse(choices_dict=result)


class AppChoicesAction:
    """应用级枚举选项视图混入，提供获取 app 下 choices.py 模块中所有枚举的接口。

    自动发现 ViewSet 所属 app 的 ``choices.py`` 模块，
    将其中所有 ``models.Choices`` 子类的枚举值通过接口暴露。

    接口：``GET /api/{res}/app-choices/``

    - 不传参数：返回所有枚举
    - ``?name=PlatformTypeChoices``：仅返回指定名称的枚举

    响应示例（不传参数）::

        {
            "code": 1000,
            "data": {
                "PlatformTypeChoices": [
                    {"value": "tencent", "label": "腾讯云"},
                    {"value": "aliyun", "label": "阿里云"}
                ],
                "CredentialTypeChoices": [
                    {"value": "access_key", "label": "Access Key 密钥对"}
                ]
            }
        }

    若 app 无 ``choices.py`` 模块，返回空字典。
    """

    queryset: Any

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='name',
                description='枚举类名，传则仅返回该枚举；不传则返回全部',
                required=False,
                type=OpenApiTypes.STR,
            ),
        ],
        responses=get_default_response_schema(
            {
                'data': build_object_type(
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
        ),
    )
    @action(methods=['get'], detail=False, url_path='app-choices')
    def app_choices(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """获取当前应用 choices.py 模块中定义的枚举选项

        支持通过 ``name`` 查询参数获取指定枚举，不传则返回全部。
        """
        target_name = request.query_params.get('name')
        result = {}
        try:
            app_label = self.queryset.model._meta.app_label
            module = importlib.import_module(f'apps.{app_label}.choices')
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, models.Choices)
                    and obj not in (models.Choices, models.TextChoices, models.IntegerChoices)
                    and obj.__module__ == module.__name__
                ):
                    if target_name and name != target_name:
                        continue
                    result[name] = get_choices_dict(obj.choices)
        except ModuleNotFoundError:
            pass  # app 没有 choices.py 模块
        except Exception as e:
            logger.error(f'get app-choices failed: {e}')
        return ApiResponse(data=result)


class SearchFieldsAction:
    """搜索字段视图混入，提供获取查询字段定义的接口。"""

    filterset_class: Callable

    @extend_schema(
        responses=get_default_response_schema(
            {
                'data': build_array_type(
                    build_object_type(
                        properties={
                            'key': build_basic_type(OpenApiTypes.STR),
                            'label': build_basic_type(OpenApiTypes.STR),
                            'help_text': build_basic_type(OpenApiTypes.STR),
                            'default': build_basic_type(OpenApiTypes.ANY),
                            'input_type': build_basic_type(OpenApiTypes.STR),
                            'choices': build_array_type(
                                build_object_type(
                                    properties={
                                        'pk': build_basic_type(OpenApiTypes.STR),
                                        'value': build_basic_type(OpenApiTypes.STR),
                                        'label': build_basic_type(OpenApiTypes.STR),
                                    }
                                )
                            ),
                        }
                    )
                )
            }
        )
    )
    @action(methods=['get'], detail=False, url_path='search-fields')
    def search_fields(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """获取{cls}的查询字段"""
        results = []
        try:
            filterset_class = self.filterset_class.get_filters()
            filter_fields = self.filterset_class.get_fields().keys()
            for field_name, value in filterset_class.items():
                if field_name not in filter_fields:
                    continue
                widget = value.field.widget
                if isinstance(widget, SelectMultiple):
                    widget.input_type = 'select-multiple'
                if isinstance(widget, DateRangeWidget):
                    widget.input_type = 'datetimerange'
                if isinstance(widget, DateTimeInput):
                    widget.input_type = 'datetime'
                # if hasattr(value.field, 'queryset'):  # 将一些具有关联的字段的数据置空
                #     widget.input_type = 'text'
                #     widget.choices = []
                widget.input_type = get_format_intput_type(value, widget.input_type)
                choices = list(getattr(widget, 'choices', []))
                if choices and len(choices) > 0 and choices[0][0] == '':
                    choices.pop(0)
                field = get_model_field(self.filterset_class._meta.model, value.field_name)
                results.append(
                    {
                        'key': field_name,
                        'label': value.label
                        if value.label
                        else (getattr(field, 'verbose_name', field.name) if field else field_name),
                        'help_text': value.field.help_text
                        if value.field.help_text
                        else getattr(field, 'help_text', None),
                        'input_type': widget.input_type,
                        'choices': get_choices_dict(choices),
                        'default': [] if 'multiple' in widget.input_type else '',
                    }
                )
            order_choices = []
            ordering_fields = list(getattr(self, 'ordering_fields', []))
            for choice in ordering_fields:
                is_des = False
                if choice.startswith('-'):
                    choice = choice[1:]
                    is_des = True
                label = choice
                field = get_model_field(self.filterset_class._meta.model, choice)
                if field:
                    label = getattr(field, 'verbose_name', choice)
                des = (f'-{choice}', f'{label} descending')
                ase = (choice, f'{label} ascending')
                if is_des:
                    des, ase = ase, des
                order_choices.extend([des, ase])
            if order_choices:
                results.append(
                    {
                        'label': 'ordering',
                        'key': 'ordering',
                        'input_type': 'select-ordering',
                        'choices': get_choices_dict(order_choices),
                        'default': order_choices[0][0],
                    }
                )
        except Exception as e:
            logger.error(f'get search-field failed {e}')
        return ApiResponse(data=results)


class SearchColumnsAction:
    """展示字段视图混入，提供获取表格列定义的接口。"""

    filterset_class: Callable

    @extend_schema(
        responses=get_default_response_schema(
            {
                'data': build_array_type(
                    build_object_type(
                        properties={
                            'key': build_basic_type(OpenApiTypes.STR),
                            'label': build_basic_type(OpenApiTypes.STR),
                            'help_text': build_basic_type(OpenApiTypes.STR),
                            'default': build_basic_type(OpenApiTypes.ANY),
                            'input_type': build_basic_type(OpenApiTypes.STR),
                            'required': build_basic_type(OpenApiTypes.BOOL),
                            'read_only': build_basic_type(OpenApiTypes.BOOL),
                            'write_only': build_basic_type(OpenApiTypes.BOOL),
                            'multiple': build_basic_type(OpenApiTypes.BOOL),
                            'max_length': build_basic_type(OpenApiTypes.NUMBER),
                            'table_show': build_basic_type(OpenApiTypes.NUMBER),
                            'choices': build_array_type(
                                build_object_type(
                                    properties={
                                        'pk': build_basic_type(OpenApiTypes.STR),
                                        'value': build_basic_type(OpenApiTypes.STR),
                                        'label': build_basic_type(OpenApiTypes.STR),
                                    }
                                )
                            ),
                        }
                    )
                )
            }
        )
    )
    @action(methods=['get'], detail=False, url_path='search-columns')
    def search_columns(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """获取{cls}的展示字段"""
        results = []

        # def check_upload_tp(value, tp):
        #     if hasattr(value, 'child_relation'):
        #         value = value.child_relation
        #     try:
        #         if (value.queryset.model._meta.label == "system.UploadFile"
        #                 and isinstance(value, BasePrimaryKeyRelatedField)
        #                 and tp in ['object_related_field', 'm2m_related_field']):
        #             return tp + "_file"
        #     except Exception:
        #         pass
        #     return tp

        def get_input_type(value: Any, info: dict) -> str:
            """根据字段对象和信息字典推断输入类型。

            Args:
                value: 序列化器字段对象。
                info: 字段信息字典。

            Returns:
                输入类型字符串。
            """
            if hasattr(value, 'child_relation') and isinstance(value.child_relation, BasePrimaryKeyRelatedField):
                info['multiple'] = True
                value.child_relation.is_column = True
                tp = get_format_intput_type(value.child_relation, info['type'])
            else:
                tp = get_format_intput_type(value, info['type'])
            if tp and tp.endswith('related_field'):
                value.is_column = True
                info['choices'] = json.loads(json.dumps(value.choices, cls=encoders.JSONEncoder))
                # info['choices'] = [{'value': k, 'label': v} for k, v in value.choices.items()]
            return tp

        metadata_class = self.metadata_class()
        serializer = self.get_serializer()
        fields = getattr(serializer, 'fields', [])
        meta = getattr(serializer, 'Meta', {})
        table_fields = getattr(meta, 'table_fields', [])
        tabs_fields = getattr(meta, 'tabs', [])
        tabs_label = []
        tabs_info = {}
        if tabs_fields:
            index = 0
            for tabs in tabs_fields:
                tabs_label.append(tabs.label)
                for field in tabs.fields:
                    tabs_info[field] = index
                index += 1

        for key, value in fields.items():
            info = metadata_class.get_field_info(value)
            if hasattr(meta, 'model'):
                field = get_model_field(meta.model, value.source)
            else:
                field = None
            info['key'] = key
            if info.get('help_text', None) is None and hasattr(field, 'help_text'):
                info['help_text'] = field.help_text

            if value.field_name.replace('_', ' ').capitalize() == info['label'] and hasattr(field, 'verbose_name'):
                info['label'] = field.verbose_name

            if isinstance(value, CharField) and value.style.get('base_template', '') == 'textarea.html':
                info['input_type'] = 'textarea'
            else:
                info['input_type'] = get_input_type(value, info)
            del info['type']
            if not table_fields:
                info['table_show'] = 1
            if key in table_fields:
                info['table_show'] = (table_fields.index(key)) + 1
            if tabs_info and tabs_label:
                info['tabs_index'] = tabs_info.get(key, 0)
                info['tabs_label'] = tabs_label[info['tabs_index']]
            # 根据 ViewSet 的 ordering_fields 判断该列是否支持排序
            ordering_fields: list = getattr(self, 'ordering_fields', []) or []
            info['sortable'] = key in ordering_fields or key in [f.lstrip('-') for f in ordering_fields]
            results.append(info)
        return ApiResponse(data=results)


class BaseViewSet:
    """基础视图集，提供通用的查询、分页、序列化器选择逻辑。"""

    action: Callable
    extra_filter_class = []

    def perform_destroy(self, instance: Any) -> Any:
        """执行实例删除操作。

        Args:
            instance: 待删除的模型实例。

        Returns:
            删除操作的返回值。
        """
        return instance.delete()

    def filter_queryset(self, queryset: Any) -> Any:
        """根据配置的过滤器后端过滤查询集。

        Args:
            queryset: 原始查询集。

        Returns:
            过滤后的查询集。
        """
        for backend in set(set(self.filter_backends) | set(self.extra_filter_class or [])):
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset

    def get_queryset(self) -> Any:
        """获取查询集，优先返回 values_queryset（若存在）。"""
        if getattr(self, 'values_queryset', None):
            return self.values_queryset
        return super().get_queryset()

    def paginate_queryset(self, queryset: Any) -> Any:
        """对查询集进行分页，文件导出时跳过分页。

        Args:
            queryset: 原始查询集。

        Returns:
            分页后的数据，文件导出时返回 None。
        """
        # 文件导出的时候，忽略 paginate_queryset
        if self.request.query_params.get('type') in ['csv', 'xlsx'] and self.request.path_info.endswith('export-data'):
            return None
        return super().paginate_queryset(queryset)

    def get_serializer_class(self) -> Any:
        """根据当前 action 动态选择序列化器类。"""
        action_serializer_name = f'{self.action}_serializer_class'
        action_serializer_class = getattr(self, action_serializer_name, None)
        if action_serializer_class:
            return action_serializer_class
        return super().get_serializer_class()


class BatchDestroyAction:
    """批量删除视图混入，提供按主键列表批量删除的接口。"""

    filter_queryset: Callable
    get_queryset: Callable
    perform_destroy: Callable

    @extend_schema(
        request=OpenApiRequest(build_array_type(build_basic_type(OpenApiTypes.STR))),
        responses=get_default_response_schema(),
    )
    @action(methods=['post'], detail=False, url_path='batch-destroy')
    def batch_destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """批量删除{cls}"""

        # response = run_view_by_celery_task(self, request, kwargs, request.data, batch_length=30)
        # if response:
        #     return response

        # queryset  delete() 方法进行批量删除，并不调用模型上的任何 delete() 方法,需要通过循环对象进行删除
        count = 0
        for instance in self.filter_queryset(self.get_queryset()).filter(pk__in=request.data):
            try:
                deleted, _rows_count = self.perform_destroy(instance)
                if deleted:
                    count += 1
            except Exception as e:
                logger.error(f'failed to destroy instance {instance} with error {e}')
        return ApiResponse(detail=_('Operation successful. Batch deleted {} data').format(count))


class CreateAction(mixins.CreateModelMixin):
    """创建视图混入，封装创建接口返回为 ``ApiResponse``。"""

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """添加{cls}数据"""
        data = super().create(request, *args, **kwargs).data
        return ApiResponse(data=data)


class DetailAction(mixins.RetrieveModelMixin):
    """详情视图混入，封装详情接口返回为 ``ApiResponse``。"""

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """获取{cls}的详情"""
        data = super().retrieve(request, *args, **kwargs).data
        return ApiResponse(data=data)


class ListAction(mixins.ListModelMixin):
    """列表视图混入，封装列表接口返回为 ``ApiResponse``。"""

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """获取{cls}的列表"""
        data = super().list(request, *args, **kwargs).data
        return ApiResponse(data=data)


class DestroyAction(mixins.DestroyModelMixin):
    """删除视图混入，封装删除接口返回为 ``ApiResponse``。"""

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """删除{cls}数据"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return ApiResponse()


class UpdateAction(mixins.UpdateModelMixin):
    """更新视图混入，封装更新接口返回为 ``ApiResponse``。"""

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """整体更新{cls}信息"""
        data = super().update(request, *args, **kwargs).data
        return ApiResponse(data=data)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """部分更新{cls}信息"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


class OnlyExportDataAction(ListAction):
    """仅导出数据视图混入，提供 Excel/CSV 导出接口。"""

    @extend_schema(
        parameters=[
            OpenApiParameter(name='type', required=True, enum=['xlsx', 'csv']),
        ],
        responses={200: OpenApiResponse(build_basic_type(OpenApiTypes.BINARY))},
    )
    @action(methods=['get'], detail=False, url_path='export-data')
    def export_data(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """导出{cls}数据"""
        self.format_kwarg = request.query_params.get('type', 'xlsx')
        request.no_cache = True  # 防止自定义缓存数据
        self.renderer_classes = [ExcelFileRenderer, CSVFileRenderer]
        request.accepted_renderer = None
        data = self.list(request, *args, **kwargs)
        return data


class ImportExportDataAction(CreateAction, UpdateAction, OnlyExportDataAction):
    """导入导出数据视图混入，提供数据导入及导出功能。"""

    filter_queryset: Callable
    get_queryset: Callable
    get_serializer: Callable

    @extend_schema(
        parameters=[
            OpenApiParameter(name='action', required=True, enum=['create', 'update']),
        ],
        request=OpenApiRequest(
            build_basic_type(OpenApiTypes.BINARY),
        ),
        responses={200: OpenApiResponse(build_basic_type(OpenApiTypes.BINARY))},
    )
    @action(methods=['post'], detail=False, url_path='import-data')
    @transaction.atomic
    def import_data(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """导入{cls}数据"""

        task = kwargs.get(
            'task', request.query_params.get('task', 'true').lower() in ['true', '1', 'yes']
        )  # 默认为任务异步导入
        data = request.data

        # 处理数据格式，确保是列表格式
        if isinstance(data, dict):
            data = [data]

        # 检查是否存在自关联依赖
        self_field = has_self_fields(self.queryset.model, data[0].keys()) if data else None

        # 如果存在依赖关系，则对数据进行拓扑排序
        if self_field:
            data = topological_sort(data, parent=self_field)

        # 尝试使用异步任务导入
        if task and data:
            batch_length = 99999999 if self_field else 100
            response = run_view_by_celery_task(self, request, kwargs, data, batch_length)
            if response:
                return response

        # 同步导入数据
        act = request.query_params.get('action')
        ignore_error = request.query_params.get('ignore_error', 'false') == 'true'
        if act and data:
            count = 0
            if act == 'create':
                for item in data:
                    serializer = self.get_serializer(data=item)
                    serializer.is_valid(raise_exception=not ignore_error)
                    if serializer.errors and ignore_error:
                        continue
                    self.perform_create(serializer)
                    count += 1
            elif act == 'update':
                queryset = self.filter_queryset(self.get_queryset())
                for item in data:
                    instance = queryset.filter(pk=item.get('pk')).first()
                    if not instance:
                        continue
                    serializer = self.get_serializer(instance, data=item, partial=True)
                    serializer.is_valid(raise_exception=not ignore_error)
                    if serializer.errors and ignore_error:
                        continue
                    self.perform_update(serializer)
                    count += 1
            return ApiResponse(detail=_('Operation successful. Import {} data').format(count))
        return ApiResponse(detail=_('Operation failed. Abnormal data'), code=1001)


class DetailUpdateModelSet(BaseViewSet, UpdateAction, DetailAction, GenericViewSet):
    """仅支持详情和更新的视图集。"""

    pass


class OnlyListModelSet(
    BaseViewSet, ListAction, SearchFieldsAction, SearchColumnsAction, AppChoicesAction, GenericViewSet
):
    """仅支持列表查询及搜索字段查询的视图集。"""

    pass


# 全部 ViewSet 包含增删改查
class BaseModelSet(
    BaseViewSet,
    CreateAction,
    DestroyAction,
    UpdateAction,
    ListAction,
    DetailAction,
    SearchFieldsAction,
    SearchColumnsAction,
    AppChoicesAction,
    BatchDestroyAction,
    GenericViewSet,
):
    """全部功能视图集，包含增删改查及搜索字段等。"""

    pass


# 只允许读和删除，不允许创建和修改
class ListDeleteModelSet(
    BaseViewSet,
    DestroyAction,
    ListAction,
    DetailAction,
    SearchFieldsAction,
    SearchColumnsAction,
    AppChoicesAction,
    BatchDestroyAction,
    GenericViewSet,
):
    """仅支持读和删除的视图集。"""

    pass


class NoDetailModelSet(BaseViewSet, UpdateAction, DetailAction, SearchColumnsAction, GenericViewSet):
    """无详情路由的视图集，支持更新和搜索列。"""

    pass
