"""演示应用的视图集。"""
# Create your views here.

from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.pagination import DynamicPageNumber
from apps.common.core.response import ApiResponse
from apps.common.utils import get_logger
from apps.demo.filters import BookViewSetFilter
from apps.demo.models import Book
from apps.demo.serializers.book import BookSerializer

logger = get_logger(__name__)


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
