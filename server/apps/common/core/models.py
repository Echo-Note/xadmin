#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : models
# author : ly_13
# date : 12/20/2023
"""基础模型定义模块，提供 UUID/Char 主键模型、审计模型及文件自动清理混入。"""
import os
import time
import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from apps.common.utils import get_logger

logger = get_logger(__name__)


class DbUuidModel(models.Model):
    """使用 UUID 作为主键的抽象模型基类。"""

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, verbose_name=_("ID"))

    class Meta:
        """元数据配置，声明为抽象模型。"""

        abstract = True


class DbCharModel(models.Model):
    """使用 CharField 作为主键的抽象模型基类。"""

    id = models.CharField(primary_key=True, max_length=128, verbose_name=_("ID"))

    class Meta:
        """元数据配置，声明为抽象模型。"""

        abstract = True


class AutoCleanFileMixin(object):
    """
    当对象包含文件字段，更新或者删除的时候，自动删除底层文件
    """

    def save(self, *args: Any, **kwargs: Any) -> Any:
        """保存对象，更新时自动清理被替换的旧文件。

        Args:
            *args: 透传给父类 save 的位置参数。
            **kwargs: 透传给父类 save 的关键字参数。

        Returns:
            父类 save 的返回值。
        """
        if kwargs.get('force_insert', None):
            filelist = []
        else:
            filelist = self.__get_filelist(self._meta.model.objects.filter(pk=self.pk).first())
        result = super().save(*args, **kwargs)
        self.__delete_file(filelist, True)
        return result

    def delete(self, *args: Any, **kwargs: Any) -> Any:
        """删除对象，并自动清理关联的文件及关联表中的文件记录。

        Args:
            *args: 透传给父类 delete 的位置参数。
            **kwargs: 透传给父类 delete 的关键字参数。

        Returns:
            父类 delete 的返回值。
        """
        filelist = self.__get_filelist()
        related_filelist = self.__get_related_filelist()
        result = super().delete(*args, **kwargs)
        self.__delete_file(filelist)
        self.__delete_related_files(related_filelist)
        return result

    def __delete_file(self, filelist: list, is_save: bool = False) -> None:
        """删除文件列表中的文件。

        Args:
            filelist: 文件信息列表，每项为 (字段名, 文件名, 文件对象) 元组。
            is_save: 是否为保存场景，保存时跳过未变更的文件。
        """
        try:
            for item in filelist:
                if is_save:
                    file = getattr(self, item[0], None)
                    if file and file.name == item[1]:
                        continue
                item[2].name = item[1]
                item[2].delete(save=False)
        except Exception as e:
            logger.warning(f"remove {self} old file {filelist} failed, {e}")

    def __get_filelist(self, obj: Any = None) -> list:
        """获取对象中所有文件类型字段的文件信息。

        Args:
            obj: 模型实例，为 None 时使用 self。

        Returns:
            文件信息列表，每项为 (字段名, 文件名, 文件对象) 元组。
        """
        filelist = []
        if obj is None:
            obj = self
        for field in obj._meta.fields:
            if isinstance(field, (models.ImageField, models.FileField)) and hasattr(obj, field.name):
                file_obj = getattr(obj, field.name, None)
                if file_obj:
                    filelist.append((field.name, file_obj.name, file_obj))
        return filelist

    def __get_related_filelist(self, obj: Any = None) -> list:
        """获取对象关联的 UploadFile 模型文件列表。

        Args:
            obj: 模型实例，为 None 时使用 self。

        Returns:
            关联文件对象列表。
        """
        filelist = []
        if obj is None:
            obj = self
        for field in obj._meta.get_fields():
            if field.is_relation and field.related_model._meta.label == "system.UploadFile":
                file_data = getattr(obj, field.name, None)
                if isinstance(field, models.ManyToManyField):
                    file_data = file_data.all()
                if isinstance(file_data, (list, QuerySet)):
                    filelist.extend(file_data)
                else:
                    filelist.append(file_data)
        return filelist

    def __delete_related_files(self, filelist: list) -> None:
        """删除关联文件列表中的所有文件。

        Args:
            filelist: 关联文件对象列表。
        """
        for file in filelist:
            file.delete()

class DbBaseModel(models.Model):
    """基础模型，包含创建时间、更新时间和描述字段。"""

    created_time = models.DateTimeField(auto_now_add=True, verbose_name=_("Created time"), null=True, blank=True)
    updated_time = models.DateTimeField(auto_now=True, verbose_name=_("Updated time"), null=True, blank=True)
    description = models.CharField(max_length=256, verbose_name=_("Description"), null=True, blank=True)

    class Meta:
        """元数据配置，声明为抽象模型。"""

        abstract = True


class DbAuditModel(DbBaseModel):
    """审计模型，在基础模型上增加创建人、修改人及数据归属部门字段。"""

    creator = models.ForeignKey(to=settings.AUTH_USER_MODEL, related_query_name='creator_query', null=True, blank=True,
                                verbose_name=_("Creator"), on_delete=models.SET_NULL, related_name='+')
    modifier = models.ForeignKey(to=settings.AUTH_USER_MODEL, related_query_name='modifier_query', null=True,
                                 blank=True, verbose_name=_("Modifier"), on_delete=models.SET_NULL, related_name='+')
    dept_belong = models.ForeignKey(to="system.DeptInfo", related_query_name='dept_belong_query', null=True, blank=True,
                                    verbose_name=_("Data ownership department"), on_delete=models.SET_NULL,
                                    related_name='+')

    class Meta:
        """元数据配置，声明为抽象模型。"""

        abstract = True


def upload_directory_path(instance: Any, filename: str) -> str:
    """生成文件上传的存储路径。

    路径格式为 ``<app>/<model>/<creator_pk>/<instance_pk>/<新文件名>``，
    新文件名基于时间戳和 UUID v5 生成以避免冲突。

    Args:
        instance: 模型实例对象。
        filename: 原始文件名。

    Returns:
        拼接好的相对存储路径。
    """
    prefix = filename.split('.')[-1]
    tmp_name = f"{filename}_{time.time()}"
    new_filename = f"{uuid.uuid5(uuid.NAMESPACE_DNS, tmp_name).__str__().replace('-', '')}.{prefix}"
    labels = instance._meta.label_lower.split('.')
    if creator := getattr(instance, "creator", None):
        creator_pk = creator.pk
    else:
        creator_pk = 0
    return os.path.join(labels[0], labels[1], str(creator_pk), str(instance.pk if instance.pk else 0), new_filename)
