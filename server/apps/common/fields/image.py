#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : image
# author : ly_13
# date : 1/17/2024
"""图片处理字段及缩略图生成工具。"""
import os

from django.core.files import File
from django.core.files.storage import default_storage, FileSystemStorage
from django.db import models
from django.db.models.fields.files import ImageFieldFile
from imagekit.cachefiles import ImageCacheFile
from imagekit.models.fields import SpecHostField
from imagekit.specs import SpecHost
from imagekit.utils import generate
from pilkit.processors import ResizeToFill
from pilkit.utils import suggest_extension


def source_name(generator: SpecHost, index: int) -> str:
    """生成缩略图文件名。

    Args:
        generator: 图片规格生成器。
        index: 缩放索引。

    Returns:
        缩略图文件名。
    """
    source_filename = getattr(generator.source, 'name', None)
    ext = suggest_extension(source_filename or '', generator.format)
    return f"{os.path.splitext(source_filename)[0]}_{index}{ext}"


def get_thumbnail(source: ImageFieldFile, index: int, force: bool = False) -> str:
    """获取指定缩放索引的缩略图文件名。

    Args:
        source: 原始图片文件对象。
        index: 缩放索引。
        force: 是否强制重新生成。

    Returns:
        缩略图文件名。
    """
    scales = source.field.scales
    # spec = ImageSpec(source)
    spec = source.field.get_spec(source=source)
    width = spec.processors[0].width
    height = spec.processors[0].height
    spec.format = 'JPEG'
    spec.options = {'quality': 90}
    if index not in scales:
        index = scales[-1]
    spec.processors = [ResizeToFill(int(width / index), int(height / index))]
    file = ImageCacheFile(spec, name=source_name(spec, index))
    file.generate(force=force)
    return file.name


class ProcessedImageFieldFile(ImageFieldFile):
    """处理后的图片字段文件对象。"""

    is_local_storage = isinstance(default_storage, FileSystemStorage)

    def save(self, name: str, content: File, save: bool = True) -> str:
        """保存图片文件，保存前执行图片处理。

        Args:
            name: 文件名。
            content: 文件内容。
            save: 是否保存关联模型实例。

        Returns:
            保存后的文件名。
        """
        filename, ext = os.path.splitext(name)
        spec = self.field.get_spec(source=content)
        ext = suggest_extension(name, spec.format)
        new_name = '%s%s' % (filename, ext)
        content = generate(spec)
        return super().save(new_name, content, save)

    def delete(self, save: bool = True) -> None:
        """删除图片文件及其缩略图。"""
        # Clear the image dimensions cache
        if hasattr(self, "_dimensions_cache"):
            del self._dimensions_cache
        name = self.name
        if self.is_local_storage:
            try:
                for i in self.field.scales:
                    self.name = f"{name.split('.')[0]}_{i}.jpg"
                    super().delete(False)
            except Exception as e:
                pass
        self.name = name
        super().delete(save)

    @property
    def url(self) -> str:
        """获取图片访问 URL，本地存储 PNG 替换为缩略图。"""
        url: str = super().url
        if self.is_local_storage and url.endswith('.png'):
            return url.replace('.png', '_1.jpg')
        return url


class ProcessedImageField(models.ImageField, SpecHostField):
    """
    ProcessedImageField is an ImageField that runs processors on the uploaded
    image *before* saving it to storage. This is in contrast to specs, which
    maintain the original. Useful for coercing fileformats or keeping images
    within a reasonable size.

    """
    attr_class = ProcessedImageFieldFile

    def __init__(self, processors: list | None = None, format: str | None = None,
                 options: dict | None = None, scales: list | None = None,
                 verbose_name: str | None = None, name: str | None = None,
                 width_field: str | None = None, height_field: str | None = None,
                 autoconvert: bool | None = None, spec: SpecHost | None = None,
                 spec_id: str | None = None, **kwargs) -> None:
        """
        The ProcessedImageField constructor accepts all of the arguments that
        the :class:`django.db.models.ImageField` constructor accepts, as well
        as the ``processors``, ``format``, and ``options`` arguments of
        :class:`imagekit.models.ImageSpecField`.

        """
        # if spec is not provided then autoconvert will be True by default
        if spec is None and autoconvert is None:
            autoconvert = True

        self.scales = scales if scales is not None else [1]
        self.format = format if format else 'png'

        SpecHost.__init__(self, processors=processors, format=self.format,
                          options=options, autoconvert=autoconvert, spec=spec,
                          spec_id=spec_id)
        models.ImageField.__init__(self, verbose_name, name, width_field,
                                   height_field, **kwargs)

    def contribute_to_class(self, cls: type, name: str) -> None:
        """将字段注册到模型类并设置 spec_id。

        Args:
            cls: 模型类。
            name: 字段名。
        """
        self._set_spec_id(cls, name)
        return super().contribute_to_class(cls, name)

