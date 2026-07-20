"""域名管理应用的配置。"""

from django.apps import AppConfig


class DomainConfig(AppConfig):
    """域名管理应用配置类。

    管理域名资产、DNS 解析记录、备案信息（ICP/公安）、SSL 证书等领域名相关的资产业务。
    从 apps.asset 拆分独立，数据库表名保持不变（asset_*）以兼容历史数据。
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.domain'
    verbose_name = '域名管理'

    def ready(self) -> None:
        """应用就绪时导入信号处理器。"""
        from . import signals  # noqa: F401

        super().ready()
