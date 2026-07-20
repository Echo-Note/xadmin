"""资产管理应用的配置。

域名相关功能（Domain/Filing/SslCertificate/DnsRecord）已迁移至独立应用 apps.domain。
本应用仅保留云服务器、本地物理服务器、本地虚拟主机管理。
"""

from django.apps import AppConfig


class AssetConfig(AppConfig):
    """资产管理应用配置类。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.asset'
    verbose_name = '资产管理'

    def ready(self) -> None:
        """应用就绪时执行初始化。"""
        super().ready()
