"""公司主体管理应用的枚举 choices 定义。"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class CompanyTypeChoices(models.TextChoices):
    """公司类型枚举。"""

    LIMITED_LIABILITY = 'limited_liability', _('有限责任公司')
    JOINT_STOCK = 'joint_stock', _('股份有限公司')
    SOLE_PROPRIETORSHIP = 'sole_proprietorship', _('个人独资企业')
    PARTNERSHIP = 'partnership', _('合伙企业')
    INDIVIDUAL_BUSINESS = 'individual_business', _('个体工商户')
    OTHER = 'other', _('其他')
