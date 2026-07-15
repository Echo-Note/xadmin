"""公司主体管理的视图集。"""

from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.company.filters import CompanyFilter
from apps.company.models import Company
from apps.company.serializers import CompanySerializer


class CompanyViewSet(BaseModelSet, ImportExportDataAction):
    """公司主体管理，支持导入导出。

    证照文件（营业执照、法人身份证正反面）通过表单 multipart/form-data 随 Company
    create/update 一起提交，由 Django UploadHandler 保证原子性：校验失败自动清理临时文件。
    """

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filterset_class = CompanyFilter
    ordering_fields = ['name', 'created_time']
