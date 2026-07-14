"""系统设置模型定义。"""

import json
from typing import Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.base.utils import signer
from apps.common.core.models import DbAuditModel, DbUuidModel
from apps.system.models import UserInfo


class Setting(DbAuditModel, DbUuidModel):
    """系统设置模型，存储各类配置项的名称、值及加密状态。"""

    name = models.CharField(max_length=128, unique=True, verbose_name=_("Name"), help_text=_("Unique configuration item name"), db_comment="设置项名称")
    value = models.TextField(verbose_name=_("Value"), null=True, blank=True, help_text=_("Configuration value, supports JSON format"), db_comment="设置项值")
    category = models.CharField(max_length=128, default="default", verbose_name=_('Category'), help_text=_("Configuration category for grouping settings"), db_comment="设置项分类")
    encrypted = models.BooleanField(default=False, verbose_name=_('Encrypted'), help_text=_("Whether the value is encrypted at rest"), db_comment="是否加密存储")
    is_active = models.BooleanField(default=True, verbose_name=_("Is active"), help_text=_("Whether this setting is active and loaded into the system"), db_comment="是否启用")

    def __str__(self):
        """返回设置项名称。"""
        return self.name

    @property
    def cleaned_value(self) -> str | None:
        """返回经过解密和 JSON 反序列化后的值。"""
        try:
            value = self.value
            if self.encrypted and value is not None:
                value = signer.decrypt(value)
            if not value:
                return None
            value = json.loads(value)
            return value
        except json.JSONDecodeError:
            return None

    @cleaned_value.setter
    def cleaned_value(self, item: list | set | str | dict | None) -> None:
        """设置值时进行 JSON 序列化，若需加密则加密存储。

        Args:
            item: 要存储的值。
        """
        try:
            if isinstance(item, set):
                item = list(item)
            v = json.dumps(item)
            if self.encrypted:
                v = signer.encrypt(v.encode('utf-8')).decode('utf-8')
            self.value = v
        except json.JSONDecodeError as e:
            raise ValueError("Json dump error: {}".format(str(e)))

    @classmethod
    def refresh_all_settings(cls) -> None:
        """刷新所有设置项到 Django settings。"""
        try:
            for setting in cls.objects.all():
                setting.refresh_setting()
        except Exception:
            pass

    @classmethod
    def refresh_item(cls, data: tuple) -> None:
        """将单个设置项刷新到 Django settings。

        Args:
            data: 包含设置名和值的元组。
        """
        setattr(settings, data[0], data[1])

    def refresh_setting(self) -> None:
        """将当前设置项刷新到 Django settings。"""
        setattr(settings, self.name, self.cleaned_value)

    @classmethod
    def save_to_file(cls, value: InMemoryUploadedFile) -> str:
        """将上传的文件保存到存储并返回 URL。

        Args:
            value: 上传的文件对象。

        Returns:
            文件的访问 URL。
        """
        filename = value.name
        filepath = f'upload/settings/{filename}'
        path = default_storage.save(filepath, ContentFile(value.read()))
        url = default_storage.url(path)
        return url

    @classmethod
    def update_or_create(cls, name: str = '', value: str | InMemoryUploadedFile = '', encrypted: bool = False,
                         category: str = '', user: UserInfo = None) -> Tuple[bool, 'Setting']:
        """创建或更新设置项，处理加密与文件上传。

        Args:
            name: 设置项名称。
            value: 设置值。
            encrypted: 是否加密。
            category: 设置分类。
            user: 操作用户。

        Returns:
            tuple: (是否变更, 设置实例)。
        """
        setting = cls.objects.filter(name=name).first()
        changed = False
        if not setting:
            setting = Setting(name=name, encrypted=encrypted, category=category, modifier=user, creator=user)

        if isinstance(value, InMemoryUploadedFile):
            value = cls.save_to_file(value)

        if setting.cleaned_value != value:
            setting.encrypted = encrypted
            setting.cleaned_value = value
            setting.modifier = user
            setting.save()
            changed = True
        return changed, setting

    class Meta:
        """元数据配置。"""

        verbose_name = _("System setting")
        verbose_name_plural = verbose_name
        db_table_comment = "系统设置表，存储各类配置项的名称、值及加密状态"
