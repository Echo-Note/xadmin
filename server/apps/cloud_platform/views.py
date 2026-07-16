"""云平台管理应用的视图集。

提供平台 CRUD、凭据管理、手动/定时同步触发及异步任务调度。
"""

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
from apps.cloud_platform.tasks import run_balance_sync_task, run_sync_task
from apps.common.core.modelset import BaseModelSet, ImportExportDataAction
from apps.common.core.response import ApiResponse


class CloudPlatformViewSet(BaseModelSet, ImportExportDataAction):
    """云平台实例管理，支持导入导出、余额刷新及同步触发。"""

    queryset = CloudPlatform.objects.select_related('company').prefetch_related('credentials')
    serializer_class = CloudPlatformSerializer
    filterset_class = CloudPlatformFilter
    ordering_fields = ['created_time', 'name']

    def perform_create(self, serializer) -> None:
        """创建云平台后可选触发同步。

        请求体中传入 sync_resources 参数（如 ["balance"]）
        可触发该平台的异步同步任务。
        """
        instance = serializer.save()
        sync_resources = self.request.data.get('sync_resources') if self.request else None
        if sync_resources and instance.is_active:
            user_id = str(self.request.user.pk) if self.request and self.request.user else None
            run_sync_task.delay(
                platform_id=str(instance.pk),
                sync_type='manual',
                resources=sync_resources,
                user_id=user_id,
            )

    def perform_update(self, serializer) -> None:
        """更新云平台后可选触发同步。"""
        instance = serializer.save()
        sync_resources = self.request.data.get('sync_resources') if self.request else None
        if sync_resources and instance.is_active:
            user_id = str(self.request.user.pk) if self.request and self.request.user else None
            run_sync_task.delay(
                platform_id=str(instance.pk),
                sync_type='manual',
                resources=sync_resources,
                user_id=user_id,
            )

    @action(methods=['post'], detail=True, url_path='refresh-balance')
    def refresh_balance(self, request: Request, *args, **kwargs) -> Response:
        """异步刷新云平台账户余额并写入每日快照。

        支持两种方式：
        1. 传入 account_balance 手动设置（同步执行）
        2. 传入 async=true 通过同步引擎拉取（异步执行）

        POST /api/cloud/platform/{pk}/refresh-balance/
        Body: {"account_balance": 100.50}  或  {"async": true}
        """
        instance = self.get_object()
        async_mode = request.data.get('async', False)

        # 异步模式：通过 Celery 任务调用同步引擎拉取余额
        if async_mode:
            user_id = str(request.user.pk) if request.user else None
            task = run_balance_sync_task.delay(
                platform_id=str(instance.pk),
                user_id=user_id,
            )
            return ApiResponse(
                data={'task_id': task.id, 'platform': instance.name},
                detail='余额同步任务已提交',
            )

        # 同步模式：手动设置余额值
        new_balance = request.data.get('account_balance', None)
        if new_balance is not None:
            try:
                instance.account_balance = float(new_balance)
            except (TypeError, ValueError):
                return ApiResponse(code=1001, detail='余额格式不正确，请提供有效的数字')

        instance.balance_updated_time = timezone.now()
        instance.save(update_fields=['account_balance', 'balance_updated_time'])

        today = date.today()
        AccountBalance.objects.update_or_create(
            platform=instance,
            record_date=today,
            defaults={'balance': instance.account_balance},
        )
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
        """查询最近 30 天余额历史。"""
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
        """根据 action 返回不同粒度的序列化器。"""
        if self.action in ('list',):
            return CredentialListSerializer
        return CredentialDetailSerializer

    @action(methods=['post'], detail=True, url_path='decrypt')
    def decrypt_credential(self, request: Request, *args, **kwargs) -> Response:
        """解密凭据敏感字段。"""
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
    """同步记录视图集 — CRUD + 异步手动触发同步 + 失败重试。"""

    queryset = SyncRecord.objects.select_related('platform').prefetch_related('agent_logs').all()
    serializer_class = SyncRecordSerializer
    filterset_class = SyncRecordFilter
    ordering_fields = ['created_time', 'started_at', 'finished_at', 'total_created', 'total_updated']

    @action(detail=False, methods=['post'], url_path='trigger')
    def trigger_sync(self, request: Request) -> Response:
        """异步触发云平台资源同步。

        同步任务在 Celery Worker 中执行，接口立即返回任务 ID。
        完成后自动发送系统通知。

        POST /api/cloud/sync-record/trigger/
        Body: {"platform": "<platform_pk>", "resources": ["server", "domain", "balance"]}
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
        user_id = str(request.user.pk) if request.user else None

        # 异步执行
        task = run_sync_task.delay(
            platform_id=str(platform.pk),
            sync_type=sync_type,
            resources=resources,
            user_id=user_id,
        )

        return ApiResponse(
            data={
                'task_id': task.id,
                'platform': platform.name,
                'platform_type': platform.platform_type,
                'resources': resources,
            },
            detail='同步任务已提交，完成后将发送系统通知',
        )

    @action(detail=True, methods=['post'], url_path='retry')
    def retry_sync(self, request: Request, pk: str | None = None) -> Response:
        """异步重试失败的同步记录。"""
        sync_record = self.get_object()
        if sync_record.status not in ('failed', 'partial'):
            return ApiResponse(code=400, detail='仅失败或部分成功的同步记录可重试')

        user_id = str(request.user.pk) if request.user else None

        task = run_sync_task.delay(
            platform_id=str(sync_record.platform.pk),
            sync_type='manual',
            resources=sync_record.resources,
            user_id=user_id,
        )

        return ApiResponse(
            data={
                'task_id': task.id,
                'platform': sync_record.platform.name,
                'resources': sync_record.resources,
            },
            detail='重试同步任务已提交',
        )


class SyncAgentLogViewSet(BaseModelSet):
    """同步 Agent 日志视图集 — 只读列表和详情。"""

    queryset = SyncAgentLog.objects.select_related('sync_record').all()
    serializer_class = SyncAgentLogSerializer
    filterset_class = SyncAgentLogFilter
    ordering_fields = ['created_time', 'started_at', 'finished_at']
