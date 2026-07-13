"""菜单路由视图。"""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from django.db.models import QuerySet

from apps.common.base.magic import cache_response
from apps.common.base.utils import menu_list_to_tree, format_menu_data
from apps.common.core.modelset import CacheDetailResponseMixin
from apps.common.core.permission import get_user_menu_queryset
from apps.common.core.response import ApiResponse
from apps.system.models import Menu, UserInfo
from apps.system.serializers.route import RouteSerializer


def get_auths(user: UserInfo) -> QuerySet:
    """获取用户的权限标识列表。

    Args:
        user: 用户对象。

    Returns:
        权限标识名称的查询集。
    """
    if user.is_superuser:
        menu_obj = Menu.objects.filter(is_active=True)
    else:
        menu_obj = get_user_menu_queryset(user)
    if not menu_obj:
        menu_obj = Menu.objects.none()
    return menu_obj.filter(menu_type=Menu.MenuChoices.PERMISSION).values_list('name', flat=True).distinct()


class UserRoutesAPIView(GenericAPIView, CacheDetailResponseMixin):
    """用户菜单路由视图。"""

    @extend_schema(exclude=True)
    @cache_response(timeout=3600 * 24, key_func='get_cache_key')
    def get(self, request: Request) -> Response:
        """获取当前用户的菜单路由和权限列表。"""
        route_list = []
        user_obj = request.user
        menu_type = [Menu.MenuChoices.DIRECTORY, Menu.MenuChoices.MENU]
        if user_obj.is_superuser:
            route_list = RouteSerializer(Menu.objects.filter(is_active=True, menu_type__in=menu_type).order_by('rank'),
                                         many=True, ignore_field_permission=True).data

            return ApiResponse(data=format_menu_data(menu_list_to_tree(route_list)), auths=get_auths(user_obj))
        else:
            menu_queryset = get_user_menu_queryset(user_obj)
            if menu_queryset:
                route_list = RouteSerializer(
                    menu_queryset.filter(menu_type__in=menu_type).distinct().order_by('rank'), many=True,
                    ignore_field_permission=True).data

        return ApiResponse(data=format_menu_data(menu_list_to_tree(route_list)), auths=get_auths(user_obj))
