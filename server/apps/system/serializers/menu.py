"""菜单序列化器。"""

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.common.core.serializers import BaseModelSerializer
from apps.common.utils import get_logger
from apps.system.models import Menu, MenuMeta

logger = get_logger(__name__)


class MenuMetaSerializer(BaseModelSerializer):
    """菜单元信息序列化器。"""

    class Meta:
        """序列化器元数据。"""

        model = MenuMeta
        exclude = ['creator', 'modifier', 'id']
        read_only_fields = ['creator', 'modifier', 'dept_belong', 'id']
        extra_kwargs = {
            'pk': {'read_only': True, 'label': _('ID'), 'help_text': _('Primary key ID')},
            'title': {'label': _('Menu title'), 'help_text': _('Display title of the menu')},
            'icon': {'label': _('Left icon'), 'help_text': _('Icon displayed to the left of the menu name')},
            'r_svg_name': {'label': _('Right icon'),
                           'help_text': _('Additional icon to the right of menu name')},
            'is_show_menu': {'label': _('Show menu'), 'help_text': _('Whether the menu is visible in the sidebar')},
            'is_show_parent': {'label': _('Show parent menu'),
                               'help_text': _('Whether to show the parent menu when this menu is active')},
            'is_keepalive': {'label': _('Keepalive'),
                             'help_text': _('When enabled, the entire state of the page is saved, and when refreshed, the state is cleared')},
            'frame_url': {'label': _('Iframe URL'), 'help_text': _('The embedded iframe link address')},
            'frame_loading': {'label': _('Iframe loading'),
                              'help_text': _('Whether the iframe shows a loading indicator')},
            'transition_enter': {'label': _('Enter animation'),
                                 'help_text': _('Animation played when entering the menu page')},
            'transition_leave': {'label': _('Leave animation'),
                                 'help_text': _('Animation played when leaving the menu page')},
            'is_hidden_tag': {'label': _('Hidden tag'),
                               'help_text': _('The current menu name or custom information is prohibited from being added to the TAB')},
            'fixed_tag': {'label': _('Fixed tag'),
                          'help_text': _('Whether the current menu name is fixed to the TAB and cannot be closed')},
            'dynamic_level': {'label': _('Dynamic level'),
                               'help_text': _('Maximum number of dynamic routes that can be opened')},
            'description': {'label': _('Description'), 'help_text': _('Description of the menu meta')},
            'created_time': {'label': _('Created time'), 'help_text': _('Creation time of the menu meta')},
            'updated_time': {'label': _('Updated time'), 'help_text': _('Last update time of the menu meta')},
            'dept_belong': {'label': _('Data ownership department'),
                            'help_text': _('Department to which the menu meta data belongs')},
        }

    pk = serializers.UUIDField(source='id', read_only=True, label=_('ID'),
                               help_text=_('Primary key ID'))


class MenuSerializer(BaseModelSerializer):
    """菜单序列化器，嵌套元信息序列化。"""

    meta = MenuMetaSerializer(label=_('Menu meta'),
                              help_text=_('Menu metadata including title, icon, and display configuration'))

    class Meta:
        """序列化器元数据。"""

        model = Menu
        fields = [
            'pk', 'name', 'rank', 'path', 'component', 'meta', 'parent', 'menu_type', 'is_active', 'model', 'method'
        ]
        # read_only_fields = ['pk'] # 用于文件导入导出时，不丢失上级节点
        extra_kwargs = {
            'pk': {'read_only': True, 'label': _('ID'), 'help_text': _('Primary key ID')},
            'parent': {'attrs': ['pk', 'name'], 'allow_null': True, 'required': False,
                       'label': _('Parent menu'),
                       'help_text': _('Parent menu of the current menu, null for top-level menu')},
            'model': {'attrs': ['pk', 'name', 'label'], 'allow_null': True, 'required': False,
                      'label': _('Model'),
                      'help_text': _('Model label fields associated with the menu')},
            'name': {'label': _('Component name or permission code'),
                     'help_text': _('Unique component name for directory/menu, or permission code for permission type')},
            'rank': {'label': _('Rank'), 'help_text': _('Sort order of the menu, lower value means higher priority')},
            'path': {'label': _('Route path or api path'),
                     'help_text': _('Frontend route path for menu type, or API path for permission type')},
            'component': {'label': _('Component path'),
                          'help_text': _('Frontend component path for rendering the menu page')},
            'menu_type': {'label': _('Menu type'),
                          'help_text': _('Type of menu: directory, menu, or permission')},
            'is_active': {'label': _('Is active'), 'help_text': _('Whether the menu is active')},
            'method': {'label': _('Method'), 'help_text': _('HTTP method for permission type menu')},
        }

    def update(self, instance: Menu, validated_data: dict) -> Menu:
        """更新菜单及其元信息，在事务中执行。

        Args:
            instance: 待更新的 Menu 实例。
            validated_data: 已验证的数据字典。

        Returns:
            更新后的 Menu 实例。
        """
        with transaction.atomic():
            serializer = MenuMetaSerializer(instance.meta, data=validated_data.pop('meta'), partial=True,
                                            context=self.context)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return super().update(instance, validated_data)

    def create(self, validated_data: dict) -> Menu:
        """创建菜单及其元信息，在事务中执行。

        Args:
            validated_data: 已验证的数据字典。

        Returns:
            创建的 Menu 实例。
        """
        with transaction.atomic():
            serializer = MenuMetaSerializer(data=validated_data.pop('meta'), context=self.context)
            serializer.is_valid(raise_exception=True)
            validated_data['meta'] = serializer.save()
            return super().create(validated_data)
