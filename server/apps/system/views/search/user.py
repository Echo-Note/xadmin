"""用户搜索视图。"""

from django_filters import rest_framework as filters

from apps.common.core.filter import BaseFilterSet
from apps.common.core.modelset import OnlyListModelSet
from apps.system.models import UserInfo
from apps.system.serializers.user import UserSerializer


class SearchUserFilter(BaseFilterSet):
    """用户搜索过滤器。"""

    username = filters.CharFilter(field_name='username', lookup_expr='icontains')
    nickname = filters.CharFilter(field_name='nickname', lookup_expr='icontains')
    phone = filters.CharFilter(field_name='phone', lookup_expr='icontains')

    class Meta:
        """过滤器元数据。"""

        model = UserInfo
        fields = ['username', 'nickname', 'phone', 'email', 'is_active', 'gender', 'dept']


class SearchUserSerializer(UserSerializer):
    """用户搜索序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = UserInfo
        fields = ['pk', 'avatar', 'username', 'nickname', 'phone', 'email', 'gender', 'is_active', 'password', 'dept',
                  'description', 'last_login', 'date_joined']

        read_only_fields = [x.name for x in UserInfo._meta.fields]

        table_fields = ['pk', 'avatar', 'username', 'nickname', 'gender', 'is_active', 'dept', 'phone',
                        'last_login', 'date_joined']


class SearchUserViewSet(OnlyListModelSet):
    """用户搜索视图集。"""

    queryset = UserInfo.objects.all()
    serializer_class = SearchUserSerializer

    ordering_fields = ['date_joined', 'last_login', 'created_time']
    filterset_class = SearchUserFilter
