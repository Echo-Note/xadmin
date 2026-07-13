"""用户在线状态管理视图。"""

from django.db.models import QuerySet
from apps.common.core.filter import BaseFilterSet, PkMultipleFilter
from apps.common.core.modelset import ListDeleteModelSet, OnlyExportDataAction
from apps.common.core.pagination import DynamicPageNumber
from apps.message.utils import get_online_info, send_logout_msg
from apps.system.models import UserLoginLog
from apps.system.serializers.log import UserOnlineSerializer


class UserOnlineFilter(BaseFilterSet):
    """用户在线状态过滤器。"""

    creator_id = PkMultipleFilter(input_type='api-search-user')

    class Meta:
        """过滤器元数据。"""

        model = UserLoginLog
        fields = ['creator_id']


class UserOnlineViewSet(ListDeleteModelSet, OnlyExportDataAction):
    """用户在线状态视图集。"""

    queryset = UserLoginLog.objects.filter(login_type=UserLoginLog.LoginTypeChoices.WEBSOCKET).all()
    serializer_class = UserOnlineSerializer
    pagination_class = DynamicPageNumber(1000)
    filterset_class = UserOnlineFilter
    ordering_fields = ['created_time']

    def get_queryset(self) -> QuerySet:
        """返回当前在线用户的查询集。"""
        online_user_pks, online_user_sockets = get_online_info()
        return self.queryset.filter(creator_id__in=online_user_pks, channel_name__in=online_user_sockets)

    def perform_destroy(self, instance: UserLoginLog) -> bool:
        """删除在线用户记录并强制下线。

        Args:
            instance: UserLoginLog 模型实例。

        Returns:
            始终返回 True。
        """
        send_logout_msg(instance.creator_id, [instance.channel_name])
        return True
