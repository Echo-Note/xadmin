"""云平台管理应用的枚举 choices 定义。"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class PlatformTypeChoices(models.TextChoices):
    """云平台类型枚举。"""

    TENCENT_CLOUD = "tencent", _("腾讯云")
    ALI_CLOUD = "aliyun", _("阿里云")
    AWS = "aws", _("AWS")
    AZURE = "azure", _("Azure")
    HUAWEI_CLOUD = "huawei", _("华为云")
    VCENTER = "vcenter", _("vCenter")
    MEICHENG = "meicheng", _("美橙")
    OTHER = "other", _("其他")


class CredentialTypeChoices(models.TextChoices):
    """凭据类型枚举。"""

    ACCESS_KEY = "access_key", _("Access Key 密钥对")
    PASSWORD = "password", _("用户名/密码")
    API_TOKEN = "api_token", _("API Token")
