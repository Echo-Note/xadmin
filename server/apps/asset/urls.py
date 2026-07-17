"""资产管理应用的路由配置。"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.asset.relation_graph import RelationGraphView
from apps.asset.views import (
    CloudServerViewSet,
    DnsRecordViewSet,
    DomainViewSet,
    FilingViewSet,
    LocalServerViewSet,
    LocalVMViewSet,
)

app_name = 'asset'

router = SimpleRouter(False)

router.register('cloud-server', CloudServerViewSet, basename='asset_cloud_server')
router.register('domain', DomainViewSet, basename='asset_domain')
router.register('local-server', LocalServerViewSet, basename='asset_local_server')
router.register('local-vm', LocalVMViewSet, basename='asset_local_vm')
router.register('dns-record', DnsRecordViewSet, basename='asset_dns_record')
router.register('filing', FilingViewSet, basename='asset_filing')

urlpatterns = [
    path('relation-graph/', RelationGraphView.as_view(), name='relation_graph'),
]

urlpatterns += router.urls
