"""公司主体管理应用的配置。"""

from django.apps import AppConfig


class CompanyConfig(AppConfig):
    """公司主体管理应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.company'
    verbose_name = '公司主体管理'
