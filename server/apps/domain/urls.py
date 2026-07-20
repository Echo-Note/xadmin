"""域名管理应用的路由配置。"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.domain.relation_graph import RelationGraphView
from apps.domain.views import (
    DnsRecordViewSet,
    DomainViewSet,
    FilingViewSet,
    SslCertificateViewSet,
)

app_name = 'domain'

router = SimpleRouter(False)

router.register('domain', DomainViewSet, basename='domain_domain')
router.register('dns-record', DnsRecordViewSet, basename='domain_dns_record')
router.register('filing', FilingViewSet, basename='domain_filing')
router.register('ssl-certificate', SslCertificateViewSet, basename='domain_ssl_certificate')

urlpatterns = [
    path('relation-graph/', RelationGraphView.as_view(), name='relation_graph'),
]

urlpatterns += router.urls
