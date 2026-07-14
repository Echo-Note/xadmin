"""路由序列化器。"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import Menu, MenuMeta

logger = get_logger(__name__)


class RouteMetaSerializer(ModelSerializer):
    """路由元信息序列化器，用于前端菜单渲染。"""

    class Meta:
        """序列化器元数据。"""

        model = MenuMeta
        fields = [
            'title', 'icon', 'showParent', 'showLink', 'extraIcon', 'keepAlive', 'frameSrc', 'frameLoading',
            'transition', 'hiddenTag', 'dynamicLevel', 'fixedTag'
        ]
        extra_kwargs = {
            'title': {'label': _('Menu title'), 'help_text': _('Display title of the menu')},
            'icon': {'label': _('Left icon'), 'help_text': _('Icon displayed on the left of the menu name')},
        }

    showParent = serializers.BooleanField(source='is_show_parent', read_only=True, label=_('Show parent menu'),
                                          help_text=_('Whether to show the parent menu'))
    showLink = serializers.BooleanField(source='is_show_menu', read_only=True, label=_('Show menu'),
                                        help_text=_('Whether to show this menu'))
    extraIcon = serializers.CharField(source='r_svg_name', read_only=True, label=_('Right icon'),
                                      help_text=_('Additional icon to the right of menu name'))
    keepAlive = serializers.BooleanField(source='is_keepalive', read_only=True, label=_('Keepalive'),
                                         help_text=_('When enabled, the entire state of the page is saved, '
                                                     'and when refreshed, the state is cleared'))
    frameSrc = serializers.CharField(source='frame_url', read_only=True, label=_('Iframe URL'),
                                     help_text=_('The embedded iframe link address'))
    frameLoading = serializers.BooleanField(source='frame_loading', read_only=True, label=_('Iframe loading'),
                                            help_text=_('Whether the iframe shows a loading state'))

    transition = serializers.SerializerMethodField(label=_('Transition'),
                                                   help_text=_('Enter and leave animation configuration of the menu'))

    def get_transition(self, obj: MenuMeta) -> dict:
        """获取菜单进出动画配置。

        Args:
            obj: MenuMeta 模型实例。

        Returns:
            包含进入和离开动画名称的字典。
        """
        return {
            'enterTransition': obj.transition_enter,
            'leaveTransition': obj.transition_leave,
        }

    hiddenTag = serializers.BooleanField(source='is_hidden_tag', read_only=True, label=_('Hidden tag'),
                                         help_text=_('The current menu name or custom information is prohibited '
                                                     'from being added to the TAB'))
    fixedTag = serializers.BooleanField(source='fixed_tag', read_only=True, label=_('Fixed tag'),
                                        help_text=_('Whether the current menu name is fixed to the TAB and cannot be closed'))
    dynamicLevel = serializers.IntegerField(source='dynamic_level', read_only=True, label=_('Dynamic level'),
                                            help_text=_('Maximum number of dynamic routes that can be opened'))


class RouteSerializer(BaseModelSerializer):
    """路由序列化器，用于前端路由渲染。"""

    class Meta:
        """序列化器元数据。"""

        model = Menu
        fields = ['pk', 'name', 'rank', 'path', 'component', 'meta', 'parent']
        extra_kwargs = {
            'rank': {'read_only': True, 'label': _('Rank'), 'help_text': _('Sort order of the menu')},
            'parent': {'attrs': ['pk', 'name'], 'allow_null': True, 'required': False,
                       'label': _('Parent menu'), 'help_text': _('Parent menu of the current menu')},
            'name': {'label': _('Component name or permission code'),
                     'help_text':_('Component name or permission code, unique')},
            'path': {'label': _('Route path or api path'), 'help_text': _('Route path or API path of the menu')},
            'component': {'label': _('Component path'), 'help_text': _('Frontend component path of the menu')},
        }

    meta = RouteMetaSerializer(label=_('Menu meta'), help_text=_('Menu meta information for frontend rendering'))
