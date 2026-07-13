"""菜单搜索视图。"""

from django.utils.translation import gettext_lazy as _
from django_filters import rest_framework as filters
from rest_framework import serializers

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import OnlyListModelSet
from apps.common.core.pagination import DynamicPageNumber
from apps.system.models import Menu
from apps.system.serializers.menu import MenuSerializer


class SearchMenuFilter(BaseFilterSet):
    """菜单搜索过滤器。"""

    component = filters.CharFilter(field_name='component', lookup_expr='icontains')
    title = filters.CharFilter(field_name='meta__title', lookup_expr='icontains')
    path = filters.CharFilter(field_name='path', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = Menu
        fields = ['title', 'path', 'component']


class SearchMenuSerializer(MenuSerializer):
    """菜单搜索序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = Menu
        fields = ['title', 'pk', 'rank', 'path', 'component', 'parent', 'menu_type', 'is_active', 'method']
        table_fields = ['title', 'menu_type', 'path', 'component', 'is_active', 'method']
        read_only_fields = [x.name for x in Menu._meta.fields]

    title = serializers.CharField(source='meta.title', read_only=True, label=_('Menu title'))


class SearchMenuViewSet(OnlyListModelSet):
    """菜单搜索视图集。"""

    queryset = Menu.objects.order_by('rank').all()
    serializer_class = SearchMenuSerializer
    pagination_class = DynamicPageNumber(1000)
    ordering_fields = ['-rank', 'updated_time', 'created_time']
    filterset_class = SearchMenuFilter
