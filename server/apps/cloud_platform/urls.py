"""云平台管理应用的路由配置。"""

from rest_framework.routers import SimpleRouter

from apps.cloud_platform.views import (
    CloudPlatformViewSet,
    CredentialViewSet,
    SyncAgentLogViewSet,
    SyncRecordViewSet,
)

app_name = 'cloud_platform'

router = SimpleRouter(False)

router.register('platform', CloudPlatformViewSet, basename='cloud_platform')
router.register('credential', CredentialViewSet, basename='cloud_credential')
router.register('sync-record', SyncRecordViewSet, basename='cloud_sync_record')
router.register('sync-agent-log', SyncAgentLogViewSet, basename='cloud_sync_agent_log')

urlpatterns = []

urlpatterns += router.urls
