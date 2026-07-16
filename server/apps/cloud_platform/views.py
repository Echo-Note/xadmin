"""云平台管理应用的视图集。"""

from datetime import date

from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.cloud_platform.choices import CredentialTypeChoices
from apps.cloud_platform.filters import (
    CloudPlatformFilter,
    CredentialFilter,
    SyncAgentLogFilter,
    SyncRecordFilter,
)
from apps.cloud_platform.models import AccountBalance, CloudPlatform, Credential, SyncAgentLog, SyncRecord
from apps.cloud_platform.serializers import (
    CloudPlatformSerializer,
    CredentialDetailSerializer,
    CredentialListSerializer,
    SyncAgentLogSerializer,
    SyncRecordSerializer,
)
from apps.cloud_platform.sync.engine import SyncEngine
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.response import ApiResponse


class CloudPlatformViewSet(BaseModelSet, ImportExportDataAction):
    """云平台实例管理，支持导入导出。"""

    queryset = CloudPlatform.objects.select_related('company').prefetch_related('credentials')
    serializer_class = CloudPlatformSerializer
    filterset_class = CloudPlatformFilter
    ordering_fields = ['created_time', 'name']

    @action(methods=['post'], detail=True, url_path='refresh-balance')
    def refresh_balance(self, request: Request, *args, **kwargs) -> Response:
        """手动刷新云平台账户余额。

        1. 更新 CloudPlatform 的 account_balance 和 balance_updated_time
        2. 写入当天的 AccountBalance 每日快照（同一天多次刷新会更新同一条）
        3. 清理超过 30 天的旧快照
        """
        instance = self.get_object()
        new_balance = request.data.get('account_balance', None)

        if new_balance is not None:
            try:
                instance.account_balance = float(new_balance)
            except (TypeError, ValueError):
                return ApiResponse(code=1001, detail='余额格式不正确，请提供有效的数字')

        instance.balance_updated_time = timezone.now()
        instance.save(update_fields=['account_balance', 'balance_updated_time'])

        # 写入每日快照（同一天多次刷新会更新同一条记录）
        today = date.today()
        AccountBalance.objects.update_or_create(
            platform=instance,
            record_date=today,
            defaults={'balance': instance.account_balance},
        )

        # 清理 30 天前的旧记录
        deleted = AccountBalance.cleanup_old_records(instance.pk)

        return ApiResponse(
            data={
                'pk': instance.pk,
                'name': instance.name,
                'platform_type': instance.platform_type,
                'account_balance': str(instance.account_balance),
                'balance_updated_time': instance.balance_updated_time,
                'snapshot_date': str(today),
                'cleaned_records': deleted,
            },
            detail='余额更新成功',
        )

    @action(methods=['get'], detail=True, url_path='balance-history')
    def balance_history(self, request: Request, *args, **kwargs) -> Response:
        """查询最近 30 天余额历史。

        返回按日期倒序的 (日期, 余额) 列表，用于前端绘制余额走势图。
        """
        instance = self.get_object()
        records = (
            AccountBalance.objects.filter(platform=instance)
            .order_by('-record_date')
            .values('record_date', 'balance')[:30]
        )
        history = [{'date': str(r['record_date']), 'balance': str(r['balance'])} for r in records]
        return ApiResponse(
            data={
                'platform': instance.name,
                'current_balance': str(instance.account_balance),
                'history': history,
            }
        )


class CredentialViewSet(BaseModelSet, ImportExportDataAction):
    """云平台凭据管理，支持导入导出（敏感字段仅导入模板可见）。"""

    queryset = Credential.objects.select_related('platform')
    filterset_class = CredentialFilter
    ordering_fields = ['created_time', 'credential_name']

    def get_serializer_class(self) -> type:
        """根据 action 返回不同粒度的序列化器。

        - 列表接口使用 CredentialListSerializer（不泄露敏感信息）。
        - 详情/创建/更新使用 CredentialDetailSerializer（含加密字段）。
        """
        if self.action in ('list',):
            return CredentialListSerializer
        return CredentialDetailSerializer

    @action(methods=['post'], detail=True, url_path='decrypt')
    def decrypt_credential(self, request: Request, *args, **kwargs) -> Response:
        """解密凭据敏感字段，用于安全查看凭据明文。

        按凭据类型返回对应的敏感字段，同时返回扩展数据中可能存放的附加密钥。
        """
        instance = self.get_object()
        data: dict = {
            'pk': instance.pk,
            'credential_name': instance.credential_name,
            'credential_type': instance.credential_type,
        }

        cred_type = instance.credential_type
        if cred_type == CredentialTypeChoices.ACCESS_KEY:
            data['access_key'] = instance.access_key
            data['access_secret'] = instance.access_secret
        elif cred_type == CredentialTypeChoices.PASSWORD:
            data['username'] = instance.username
            data['password'] = instance.password
            if instance.email:
                data['email'] = instance.email
        elif cred_type == CredentialTypeChoices.API_TOKEN:
            data['api_token'] = instance.api_token
            data['token_expire_time'] = instance.token_expire_time

        if instance.extra_data:
            data['extra_data'] = instance.extra_data

        return ApiResponse(data=data, detail='凭据解密成功')


class SyncRecordViewSet(BaseModelSet, ImportExportDataAction):
    """同步记录视图集 — CRUD + 手动触发同步 + 失败重试。"""

    queryset = SyncRecord.objects.select_related('platform').prefetch_related('agent_logs').all()
    serializer_class = SyncRecordSerializer
    filterset_class = SyncRecordFilter
    ordering_fields = ['created_time', 'started_at', 'finished_at', 'total_created', 'total_updated']

    @action(detail=False, methods=['post'], url_path='trigger')
    def trigger_sync(self, request: Request) -> Response:
        """手动触发云平台资源同步。

        POST /api/cloud/sync-record/trigger/
        Body: {"platform": "<platform_pk>", "resources": ["server", "domain"]}
        """
        platform_pk = request.data.get('platform')
        if not platform_pk:
            return ApiResponse(code=400, detail='platform 参数不能为空')
        try:
            platform = CloudPlatform.objects.get(pk=platform_pk)
        except CloudPlatform.DoesNotExist:
            return ApiResponse(code=404, detail='云平台实例不存在')
        resources = request.data.get('resources')
        sync_type = request.data.get('sync_type', 'manual')
        engine = SyncEngine()
        sync_record = engine.run(platform, sync_type=sync_type, resources=resources)
        serializer = self.get_serializer(sync_record)
        return ApiResponse(data=serializer.data, detail='同步任务已完成')

    @action(detail=True, methods=['post'], url_path='retry')
    def retry_sync(self, request: Request, pk: str | None = None) -> Response:
        """重试失败的同步记录。"""
        sync_record = self.get_object()
        if sync_record.status not in ('failed', 'partial'):
            return ApiResponse(code=400, detail='仅失败或部分成功的同步记录可重试')
        engine = SyncEngine()
        new_record = engine.run(sync_record.platform, sync_type='manual', resources=sync_record.resources)
        serializer = self.get_serializer(new_record)
        return ApiResponse(data=serializer.data, detail='重试同步已完成')


class SyncAgentLogViewSet(BaseModelSet):
    """同步 Agent 日志视图集 — 只读列表和详情。"""

    queryset = SyncAgentLog.objects.select_related('sync_record').all()
    serializer_class = SyncAgentLogSerializer
    filterset_class = SyncAgentLogFilter
    ordering_fields = ['created_time', 'started_at', 'finished_at']
