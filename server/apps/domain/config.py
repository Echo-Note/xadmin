"""域名管理应用的路由与权限白名单配置。"""

from django.urls import include, path

# 路由配置，当添加 APP 完成时，会自动注入路由到总服务
URLPATTERNS = [
    path('api/domain/', include('apps.domain.urls')),
]

# 请求白名单，支持正则表达式
PERMISSION_WHITE_REURL = []
