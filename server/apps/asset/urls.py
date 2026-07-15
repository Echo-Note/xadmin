"""资产管理应用的路由配置。"""

from rest_framework.routers import SimpleRouter

from apps.asset.views import (
    CloudServerViewSet,
    DomainViewSet,
    LocalServerViewSet,
    LocalVMViewSet,
)

app_name = 'asset'

router = SimpleRouter(False)

router.register('cloud-server', CloudServerViewSet, basename='asset_cloud_server')
router.register('domain', DomainViewSet, basename='asset_domain')
router.register('local-server', LocalServerViewSet, basename='asset_local_server')
router.register('local-vm', LocalVMViewSet, basename='asset_local_vm')

urlpatterns = []

urlpatterns += router.urls
