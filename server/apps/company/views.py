"""公司主体管理的视图集。"""

from apps.common.core.modelset import BaseModelSet
from apps.company.filters import CompanyFilter
from apps.company.models import Company
from apps.company.serializers import CompanySerializer


class CompanyViewSet(BaseModelSet):
    """公司主体管理"""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter
    ordering_fields = ['name', 'created_time']
