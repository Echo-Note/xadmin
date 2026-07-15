"""演示应用的过滤器定义。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet, PkMultipleFilter
from apps.demo.models import Book


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
