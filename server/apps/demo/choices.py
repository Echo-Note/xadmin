"""演示应用的枚举 choices 定义。"""

from django.db import models


class CategoryChoices(models.IntegerChoices):
    """书籍类型枚举。"""

    DIRECTORY = 0, "小说"
    MENU = 1, "文学"
    PERMISSION = 2, "哲学"
