"""公司主体管理的视图集。"""

from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.company.filters import CompanyFilter
from apps.company.models import Company
from apps.company.serializers import CompanySerializer


class CompanyViewSet(BaseModelSet, ImportExportDataAction):
    """公司主体管理，支持导入导出。"""

    queryset = Company.objects.select_related(
        'business_license',
        'legal_representative_id_front',
        'legal_representative_id_back',
    )
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter
    ordering_fields = ['name', 'created_time']
