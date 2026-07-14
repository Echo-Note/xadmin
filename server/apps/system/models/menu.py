"""菜单模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel


class MenuMeta(DbAuditModel, DbUuidModel):
    """菜单元信息模型，存储菜单的显示、动画等配置。"""

    title = models.CharField(verbose_name=_('Menu title'), max_length=255, null=True, blank=True, help_text=_('The display title of the menu shown in the navigation bar'), db_comment="菜单标题")
    icon = models.CharField(verbose_name=_('Left icon'), max_length=255, null=True, blank=True, help_text=_('The icon name displayed on the left side of the menu item'), db_comment="菜单左侧图标")
    r_svg_name = models.CharField(verbose_name=_('Right icon'), max_length=255, null=True, blank=True,
                                  help_text=_('Additional icon to the right of menu name'),
                                  db_comment="菜单名称右侧图标")
    is_show_menu = models.BooleanField(verbose_name=_('Show menu'), default=True, help_text=_('Whether to display this menu item in the navigation'), db_comment="是否显示菜单")
    is_show_parent = models.BooleanField(verbose_name=_('Show parent menu'), default=False, help_text=_('Whether to display the parent menu item in the navigation'), db_comment="是否显示父级菜单")
    is_keepalive = models.BooleanField(verbose_name=_('Keepalive'), default=True,
                                       help_text=_(
                                           'When enabled, the entire state of the page is saved, and when refreshed, the state is cleared'),
                                       db_comment="是否开启页面缓存保活")
    frame_url = models.CharField(verbose_name=_('Iframe URL'), max_length=255, null=True, blank=True,
                                 help_text=_('The embedded iframe link address'),
                                 db_comment="内嵌iframe链接地址")
    frame_loading = models.BooleanField(verbose_name=_('Iframe loading'), default=False, help_text=_('Whether to show a loading indicator when the iframe content is being loaded'), db_comment="iframe是否显示加载状态")

    transition_enter = models.CharField(verbose_name=_('Enter animation'), max_length=255, null=True, blank=True, help_text=_('The animation name played when the page enters'), db_comment="页面进入动画名称")
    transition_leave = models.CharField(verbose_name=_('Leave animation'), max_length=255, null=True, blank=True, help_text=_('The animation name played when the page leaves'), db_comment="页面离开动画名称")

    is_hidden_tag = models.BooleanField(verbose_name=_('Hidden tag'), default=False, help_text=_(
        'The current menu name or custom information is prohibited from being added to the TAB'),
                                        db_comment="是否禁止添加到标签页")
    fixed_tag = models.BooleanField(verbose_name=_('Fixed tag'), default=False, help_text=_(
        'Whether the current menu name is fixed to the TAB and cannot be closed'),
                                    db_comment="是否固定到标签页且不可关闭")
    dynamic_level = models.IntegerField(verbose_name=_('Dynamic level'), default=0,
                                        help_text=_('Maximum number of dynamic routes that can be opened'),
                                        db_comment="可打开的动态路由最大数量")

    class Meta:
        """菜单元信息元数据。"""

        verbose_name = _('Menu meta')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        db_table_comment = "菜单元信息表，存储菜单的显示、动画等配置"

    def __str__(self) -> str:
        """返回菜单标题和描述的字符串表示。"""
        return f'{self.title}-{self.description}'


class Menu(DbAuditModel, DbUuidModel):
    """菜单模型，支持目录、菜单和权限三种类型。"""

    class MenuChoices(models.IntegerChoices):
        """菜单类型选择：目录、菜单或权限。"""

        DIRECTORY = 0, _('Directory')
        MENU = 1, _('Menu')
        PERMISSION = 2, _('Permission')

    class MethodChoices(models.TextChoices):
        """HTTP 方法选择。"""

        GET = 'GET', _('GET')
        POST = 'POST', _('POST')
        PUT = 'PUT', _('PUT')
        DELETE = 'DELETE', _('DELETE')
        PATCH = 'PATCH', _('PATCH')

    parent = models.ForeignKey('system.Menu', on_delete=models.SET_NULL, verbose_name=_('Parent menu'), null=True,
                               blank=True, help_text=_('The parent menu item, null means this is a top-level menu'),
                               db_comment="父级菜单")
    menu_type = models.SmallIntegerField(choices=MenuChoices, default=MenuChoices.DIRECTORY,
                                         verbose_name=_('Menu type'),
                                         help_text=_('Directory for grouping, menu for page routing, or permission for access control'),
                                         db_comment="菜单类型（0-目录 1-菜单 2-权限）")
    name = models.CharField(verbose_name=_('Component name or permission code'), max_length=128, unique=True, help_text=_('Unique identifier: frontend component name for menus, permission code for permission type'), db_comment="组件名或权限标识码")
    rank = models.IntegerField(verbose_name=_('Rank'), default=9999, help_text=_('Sort weight, smaller value means higher display order'), db_comment="排序权重")
    path = models.CharField(verbose_name=_('Route path or api path'), max_length=255, help_text=_('Frontend route path or backend API path for this menu'), db_comment="路由路径或API路径")
    component = models.CharField(verbose_name=_('Component path'), max_length=255, null=True, blank=True, help_text=_('The frontend component path relative to the views directory'), db_comment="前端组件路径")
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True, help_text=_('Whether this menu item is enabled and accessible'), db_comment="是否启用")
    meta = models.OneToOneField('system.MenuMeta', on_delete=models.CASCADE, verbose_name=_('Menu meta'), help_text=_('The associated menu metadata record containing display and animation settings'), db_comment="关联的菜单元信息")
    model = models.ManyToManyField('system.ModelLabelField', verbose_name=_('Model'), blank=True, help_text=_('Associated model label fields for field-level permission control'))

    # permission_marking = models.CharField(verbose_name="权限标识", max_length=255)
    # api_route = models.CharField(verbose_name="后端权限路由", max_length=255, null=True, blank=True)
    method = models.CharField(choices=MethodChoices, null=True, blank=True, verbose_name=_('Method'), max_length=10, help_text=_('HTTP method required to access this menu or API endpoint'), db_comment="HTTP方法")

    # api_auth_access = models.BooleanField(verbose_name="是否授权访问，否的话可以匿名访问后端路由", default=True)

    def delete(self, using: str | None = None, keep_parents: bool = False) -> tuple[int, dict]:
        """删除菜单时同时关联删除其元信息。

        Args:
            using: 使用的数据库别名。
            keep_parents: 是否保留父级对象。

        Returns:
            删除的数量和各模型删除数量的字典。
        """
        if self.meta:
            self.meta.delete(using, keep_parents)
        super().delete(using, keep_parents)

    class Meta:
        """菜单元数据。"""

        verbose_name = _('Menu')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)
        db_table_comment = "菜单表，支持目录、菜单和权限三种类型"

    def __str__(self) -> str:
        """返回菜单标题、类型和名称的字符串表示。"""
        return f'{self.meta.title}-{self.get_menu_type_display()}({self.name})'
