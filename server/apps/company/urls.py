"""公司主体管理应用的路由配置。"""

from rest_framework.routers import SimpleRouter

from apps.company.views import CompanyViewSet

app_name = 'company'

router = SimpleRouter(False)

router.register('company', CompanyViewSet, basename='company')

urlpatterns = []

urlpatterns += router.urls
