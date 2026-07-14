"""存储设置视图集 — 媒体文件和静态文件分离管理。"""

from apps.common.utils import get_logger
from apps.settings.serializers.storage import StorageMediaSerializer, StorageStaticSerializer
from apps.settings.views.settings import BaseSettingViewSet

logger = get_logger(__name__)


class StorageSettingViewSet(BaseSettingViewSet):
    """存储设置 — 媒体/静态文件分离管理（?category=media|static）。"""

    serializer_class = StorageMediaSerializer
    category = "storage"

    serializer_class_mapper = {
        "media": StorageMediaSerializer,
        "static": StorageStaticSerializer,
    }

    def perform_update(self, serializer: object) -> None:
        """更新后递增配置版本号，使 S3 后端感知变更。"""
        super().perform_update(serializer)
        self._bump_config_version()

    def _bump_config_version(self) -> None:
        """递增存储配置版本号并更新 Redis 缓存。"""
        from django.core.cache import caches
        from django.conf import settings
        from apps.settings.models import Setting

        try:
            current = Setting.objects.filter(name="STORAGE_CONFIG_VERSION", is_active=True).first()
            cur = int(current.cleaned_value) if current and current.cleaned_value else 0
            Setting.update_or_create(name="STORAGE_CONFIG_VERSION", value=cur + 1, category="storage")
            caches["default"].set(
                settings.CACHE_KEY_TEMPLATE["config_key"] + ":storage_version",
                cur + 1, timeout=None,
            )
        except Exception:
            pass
