"""演示应用的视图集。"""
# Create your views here.

from demo.models import Book
from demo.serializers.book import BookSerializer
from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.core.filter import BaseFilterSet, PkMultipleFilter
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.pagination import DynamicPageNumber
from apps.common.core.response import ApiResponse
from apps.common.utils import get_logger

logger = get_logger(__name__)


class BookViewSetFilter(BaseFilterSet):
    """书籍视图集的过滤器。"""

    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    author = filters.CharFilter(field_name='author', lookup_expr='icontains')
    publisher = filters.CharFilter(field_name='publisher', lookup_expr='icontains')

    # 自定义的搜索模板，针对用户搜索，前端已经内置 api-search-user 模板处理
    managers2 = PkMultipleFilter(input_type='api-search-user')

    # 自定义的搜索模板，默认是带有choices的下拉框，当数据多的话，体验不好，所以这里改为输入框，前端已经内置 input 处理
    # 关联关系搜索的时候，默认是主键pk
    managers = PkMultipleFilter(input_type='input')

    class Meta:
        """过滤器元数据配置。"""

        model = Book
        fields = ['name', 'isbn', 'author', 'publisher', 'is_active', 'publication_date', 'price',
                  'created_time', 'managers', 'managers2']  # fields用于前端自动生成的搜索表单


class BookViewSet(BaseModelSet, ImportExportDataAction):
    """书籍"""  # 这个 书籍 的注释得写， 否则菜单中可能会显示null，访问日志记录中也可能显示异常

    queryset = Book.objects.all()
    serializer_class = BookSerializer
    ordering_fields = ['created_time']
    filterset_class = BookViewSetFilter
    pagination_class = DynamicPageNumber(1000)  # 表示最大分页数据1000条，如果注释，则默认最大100条数据

    @action(methods=['post'], detail=True)
    def push(self, request: Request, *args, **kwargs) -> Response:
        """推送到其他服务"""  # 这个 推送到其他服务 的注释得写， 否则菜单中可能会显示null，访问日志记录中也可能显示异常

        # 自定义一个请求为post的 push 路由行为，执行自定义操作， action装饰器有好多参数，可以查看源码自行分析
        instance = self.get_object()
        return ApiResponse(detail=f"{instance.name} 推送成功")
