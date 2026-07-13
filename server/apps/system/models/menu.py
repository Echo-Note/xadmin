"""菜单模型。"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.core.models import DbAuditModel, DbUuidModel


class MenuMeta(DbAuditModel, DbUuidModel):
    """菜单元信息模型，存储菜单的显示、动画等配置。"""

    title = models.CharField(verbose_name=_('Menu title'), max_length=255, null=True, blank=True)
    icon = models.CharField(verbose_name=_('Left icon'), max_length=255, null=True, blank=True)
    r_svg_name = models.CharField(verbose_name=_('Right icon'), max_length=255, null=True, blank=True,
                                  help_text=_('Additional icon to the right of menu name'))
    is_show_menu = models.BooleanField(verbose_name=_('Show menu'), default=True)
    is_show_parent = models.BooleanField(verbose_name=_('Show parent menu'), default=False)
    is_keepalive = models.BooleanField(verbose_name=_('Keepalive'), default=True,
                                       help_text=_(
                                           'When enabled, the entire state of the page is saved, and when refreshed, the state is cleared'))
    frame_url = models.CharField(verbose_name=_('Iframe URL'), max_length=255, null=True, blank=True,
                                 help_text=_('The embedded iframe link address'))
    frame_loading = models.BooleanField(verbose_name=_('Iframe loading'), default=False)

    transition_enter = models.CharField(verbose_name=_('Enter animation'), max_length=255, null=True, blank=True)
    transition_leave = models.CharField(verbose_name=_('Leave animation'), max_length=255, null=True, blank=True)

    is_hidden_tag = models.BooleanField(verbose_name=_('Hidden tag'), default=False, help_text=_(
        'The current menu name or custom information is prohibited from being added to the TAB'))
    fixed_tag = models.BooleanField(verbose_name=_('Fixed tag'), default=False, help_text=_(
        'Whether the current menu name is fixed to the TAB and cannot be closed'))
    dynamic_level = models.IntegerField(verbose_name=_('Dynamic level'), default=0,
                                        help_text=_('Maximum number of dynamic routes that can be opened'))

    class Meta:
        """菜单元信息元数据。"""

        verbose_name = _('Menu meta')
        verbose_name_plural = verbose_name
        ordering = ('-created_time',)

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
                               blank=True)
    menu_type = models.SmallIntegerField(choices=MenuChoices, default=MenuChoices.DIRECTORY,
                                         verbose_name=_('Menu type'))
    name = models.CharField(verbose_name=_('Component name or permission code'), max_length=128, unique=True)
    rank = models.IntegerField(verbose_name=_('Rank'), default=9999)
    path = models.CharField(verbose_name=_('Route path or api path'), max_length=255)
    component = models.CharField(verbose_name=_('Component path'), max_length=255, null=True, blank=True)
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True)
    meta = models.OneToOneField('system.MenuMeta', on_delete=models.CASCADE, verbose_name=_('Menu meta'))
    model = models.ManyToManyField('system.ModelLabelField', verbose_name=_('Model'), blank=True)

    # permission_marking = models.CharField(verbose_name="权限标识", max_length=255)
    # api_route = models.CharField(verbose_name="后端权限路由", max_length=255, null=True, blank=True)
    method = models.CharField(choices=MethodChoices, null=True, blank=True, verbose_name=_('Method'), max_length=10)

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

    def __str__(self) -> str:
        """返回菜单标题、类型和名称的字符串表示。"""
        return f'{self.meta.title}-{self.get_menu_type_display()}({self.name})'
