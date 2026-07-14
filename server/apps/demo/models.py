"""演示应用的书籍模型。"""
from django.db import models
from django.utils import timezone
from pilkit.processors import ResizeToFill

from apps.common.core.models import AutoCleanFileMixin, DbAuditModel, upload_directory_path
from apps.common.fields.image import ProcessedImageField
from apps.system.models import UploadFile, UserInfo


class Book(AutoCleanFileMixin, DbAuditModel):
    """书籍模型，用于演示各种字段类型与关联关系。"""

    class CategoryChoices(models.IntegerChoices):
        """书籍类型枚举。"""

        DIRECTORY = 0, "小说"
        MENU = 1, "文学"
        PERMISSION = 2, "哲学"

    # choices 单选
    category = models.SmallIntegerField(choices=CategoryChoices, default=CategoryChoices.DIRECTORY,
                                        verbose_name="书籍类型", help_text="书籍分类类型：0-小说、1-文学、2-哲学", db_comment="书籍类型（0-小说 1-文学 2-哲学）")

    # ForeignKey  一对多关系
    admin = models.ForeignKey(to=UserInfo, verbose_name="管理员1", on_delete=models.CASCADE, help_text="书籍关联的管理员（一对多）", db_comment="管理员1")
    admin2 = models.ForeignKey(to=UserInfo, verbose_name="管理员2", on_delete=models.CASCADE,
                               related_name="book_admin2", help_text="书籍关联的第二管理员（一对多）", db_comment="管理员2")

    # ManyToManyField 多对多关系
    managers = models.ManyToManyField(to=UserInfo, verbose_name="操作人员1", blank=True, related_name="book_managers", help_text="书籍关联的操作人员集合（多对多）")
    managers2 = models.ManyToManyField(to=UserInfo, verbose_name="操作人员2", blank=True, related_name="book_managers2", help_text="书籍关联的第二批操作人员集合（多对多）")
    # 图片上传，原图访问
    cover = models.ImageField(verbose_name="书籍封面原图", null=True, blank=True, help_text="书籍封面原图文件，支持直接上传图片", db_comment="书籍封面原图")

    # 图片上传，压缩访问， 比如库里面存的图片是 xxx/xxx/123.png ， 压缩访问路径可以为 xxx/xxx/123_1.jpg
    # 定义了 scales=[1, 2, 3, 4] ，因此有四个压缩链接文件名  123_1.jpg 123_2.jpg 123_3.jpg 123_4.jpg
    # 原图文件名 123.png
    avatar = ProcessedImageField(verbose_name="书籍封面缩略图", null=True, blank=True,
                                 upload_to=upload_directory_path,
                                 processors=[ResizeToFill(512, 512)],  # 默认存储像素大小
                                 scales=[1, 2, 3, 4],  # 缩略图可缩小倍数，
                                 format='png', help_text="书籍封面缩略图，上传后自动压缩为512x512并提供多尺寸缩放", db_comment="书籍封面缩略图")

    # 文件上传
    book_file = models.FileField(verbose_name="书籍存储", upload_to=upload_directory_path, null=True, blank=True,
                                 help_text="书籍附件文件，支持上传任意格式文件", db_comment="书籍文件")

    # 使用 UploadFile 关联
    file = models.ForeignKey(to=UploadFile, related_name="book_file", verbose_name="书籍单个附件", blank=True,
                             on_delete=models.CASCADE, help_text="书籍关联的单个 UploadFile 附件（一对多）", db_comment="书籍单个附件")
    files = models.ManyToManyField(to=UploadFile, related_name="book_files", verbose_name="书籍多附件", blank=True, help_text="书籍关联的多个 UploadFile 附件（多对多）")

    # 普通字段
    name = models.CharField(verbose_name="书籍名称", max_length=100, help_text="书籍名称啊，随便填", db_comment="书籍名称")
    isbn = models.CharField(verbose_name="标准书号", max_length=20, help_text="书籍的 ISBN 国际标准书号", db_comment="标准书号")
    author = models.CharField(verbose_name="书籍作者", max_length=20, help_text="坐着大啊啊士大夫", db_comment="书籍作者")
    publisher = models.CharField(verbose_name="出版社", max_length=20, default='大宇出版社', help_text="书籍的出版机构名称", db_comment="出版社")
    publication_date = models.DateTimeField(verbose_name="出版日期", default=timezone.now, help_text="书籍的正式出版日期时间", db_comment="出版日期")
    price = models.FloatField(verbose_name="书籍售价", default=999.99, help_text="书籍的销售价格，单位为元", db_comment="书籍售价")
    is_active = models.BooleanField(verbose_name="是否启用", default=False, help_text="书籍是否在前台展示和销售中", db_comment="是否启用")

    class Meta:
        """书籍模型的元数据配置。"""

        verbose_name = '书籍名称'
        verbose_name_plural = verbose_name
        db_table_comment = "书籍信息表，用于演示各种字段类型与关联关系"

    def __str__(self) -> str:
        """返回书籍名称。"""
        return f"{self.name}"
