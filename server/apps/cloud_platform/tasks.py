"""云平台同步 Celery 异步任务。

提供同步操作的异步执行能力，包括：
- 手动触发同步（API 调用通过此任务异步执行）
- 每日定时余额同步
- 同步完成后自动发送系统通知
"""

from __future__ import annotations

from celery import shared_task
from django.utils.translation import gettext_lazy as _

from apps.common.celery.decorator import register_as_period_task
from apps.common.utils import get_logger
from apps.notifications.message import SiteMessageUtil
from apps.system.models import UserInfo

logger = get_logger(__name__)


def _get_admin_users():
    """获取所有超级管理员用户，用于默认通知接收人。"""
    return list(UserInfo.objects.filter(is_superuser=True, is_active=True).values_list('pk', flat=True))


def _notify_sync_result(platform_name: str, record, user_id: str | None = None) -> None:
    """根据同步结果发送系统通知。

    Args:
        platform_name: 平台名称。
        record: SyncRecord 实例。
        user_id: 触发用户 ID（手动触发时传入）。
    """
    recipients = _get_admin_users()
    if user_id:
        uid = int(user_id)
        if uid not in recipients:
            recipients.append(uid)

    status_cn = {
        'success': '成功',
        'partial': '部分成功',
        'failed': '失败',
    }.get(record.status, record.status)

    title = f'云平台同步{status_cn}: {platform_name}'
    message = (
        f'平台 [{platform_name}] 资源同步{status_cn}\n'
        f'新建: {record.total_created} | 更新: {record.total_updated} | '
        f'错误: {record.total_errors}'
    )

    if record.status == 'success':
        SiteMessageUtil.notify_success(recipients, title, message)
    elif record.status == 'failed':
        error_details = '\n'.join(e.get('error', str(e)) for e in (record.error_detail or [])[:3])
        SiteMessageUtil.notify_error(
            recipients,
            title,
            f'{message}\n错误详情:\n{error_details}',
        )
    else:
        SiteMessageUtil.notify_info(recipients, title, message)


def _record_to_dict(record) -> dict:
    """将 SyncRecord 模型实例转换为 JSON 可序列化的字典。

    Args:
        record: SyncRecord 实例或 None。

    Returns:
        包含同步结果关键字段的字典。
    """
    if record is None:
        return {'status': 'error', 'detail': 'platform not found'}
    return {
        'pk': str(record.pk),
        'platform': str(record.platform_id),
        'platform_name': getattr(record, 'platform_name', '') or record.platform.name,
        'status': record.status,
        'sync_type': record.sync_type,
        'total_created': record.total_created,
        'total_updated': record.total_updated,
        'total_terminated': record.total_terminated,
        'total_errors': record.total_errors,
        'started_at': record.started_at.isoformat() if record.started_at else None,
        'finished_at': record.finished_at.isoformat() if record.finished_at else None,
    }


def _run_sync(platform_id: str, sync_type: str, resources: list[str] | None, user_id: str | None = None):
    """内部同步执行器，供各 task 复用。

    Args:
        platform_id: CloudPlatform 主键。
        sync_type: 触发类型 (manual/scheduled)。
        resources: 同步资源类型列表。
        user_id: 触发用户 ID（手动触发时传入，用于通知）。
    """
    from apps.cloud_platform.models import CloudPlatform
    from apps.cloud_platform.sync import SyncEngine, _ensure_platforms_loaded

    _ensure_platforms_loaded()

    try:
        platform = CloudPlatform.objects.get(pk=platform_id)
    except CloudPlatform.DoesNotExist:
        logger.error('云平台不存在: %s', platform_id)
        return None

    engine = SyncEngine()
    record = engine.run(platform, sync_type=sync_type, resources=resources)

    _notify_sync_result(platform.name, record, user_id=user_id)

    logger.info(
        '同步完成 [%s]: status=%s created=%d updated=%d errors=%d',
        platform.name,
        record.status,
        record.total_created,
        record.total_updated,
        record.total_errors,
    )
    return record


# =============================================================================
# 单平台单资源同步任务 — 被 views.py 触发
# =============================================================================


@shared_task(
    name='cloud_platform.sync.run_sync_task',
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    verbose_name=_('执行云平台资源同步'),
)
def run_sync_task(
    self,
    platform_id: str,
    sync_type: str = 'manual',
    resources: list[str] | None = None,
    user_id: str | None = None,
):
    """异步执行云平台资源同步（通用入口）。

    被 API 手动触发、平台创建/更新时调用。
    执行完成后自动发送系统通知。

    Args:
        self: Celery 任务实例（bind=True）。
        platform_id: CloudPlatform 主键。
        sync_type: 触发类型。
        resources: 同步资源类型列表。
        user_id: 触发用户 ID。
    """
    logger.info(
        '开始异步同步: platform=%s type=%s resources=%s user=%s',
        platform_id,
        sync_type,
        resources,
        user_id,
    )
    try:
        record = _run_sync(platform_id, sync_type, resources, user_id=user_id)
        return _record_to_dict(record)
    except Exception as exc:
        logger.exception('同步任务异常: platform=%s', platform_id)
        # 异常时发送错误通知
        recipients = _get_admin_users()
        if user_id:
            uid = int(user_id)
            if uid not in recipients:
                recipients.append(uid)
        SiteMessageUtil.notify_error(
            recipients,
            f'云平台同步异常: #{platform_id}',
            f'同步任务执行异常: {exc}',
        )
        raise self.retry(exc=exc)


@shared_task(
    name='cloud_platform.sync.run_balance_sync_task',
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    verbose_name=_('执行云平台余额同步'),
)
def run_balance_sync_task(
    self,
    platform_id: str,
    user_id: str | None = None,
):
    """异步执行单个平台的余额同步。

    用于手动刷新余额或创建/更新平台后触发。

    Args:
        self: Celery 任务实例。
        platform_id: CloudPlatform 主键。
        user_id: 触发用户 ID。
    """
    logger.info('开始异步余额同步: platform=%s', platform_id)
    try:
        record = _run_sync(platform_id, 'manual', ['balance'], user_id=user_id)
        return _record_to_dict(record)
    except Exception as exc:
        logger.exception('余额同步异常: platform=%s', platform_id)
        raise self.retry(exc=exc)


# =============================================================================
# 每日定时余额同步任务
# =============================================================================


@shared_task(
    name='cloud_platform.sync.daily_balance_sync',
    verbose_name=_('每日定时同步所有云平台余额'),
)
@register_as_period_task(
    crontab='30 9 * * *',
    description='每天早上 9:30 同步所有启用平台的账户余额',
)
def daily_balance_sync_task() -> dict:
    """每日定时任务：同步所有启用云平台的账户余额。

    遍历所有 is_active=True 且支持 balance 同步的平台，
    逐个调用 SyncEngine 执行余额同步，汇总结果后发送通知。
    """
    from apps.cloud_platform.models import CloudPlatform, SyncRecord
    from apps.cloud_platform.sync import SyncEngine, _ensure_platforms_loaded

    _ensure_platforms_loaded()

    platforms = CloudPlatform.objects.filter(is_active=True)
    if not platforms:
        logger.info('无活跃云平台，跳过每日余额同步')
        return {'synced': 0, 'errors': 0}

    results: list[SyncRecord] = []
    for platform in platforms:
        try:
            engine = SyncEngine()
            record = engine.run(platform, sync_type='scheduled', resources=['balance'])
            results.append(record)
        except Exception:
            logger.exception('每日余额同步失败: %s', platform.name)

    # 汇总通知
    success_count = sum(1 for r in results if r.status == 'success')
    total_errors = sum(r.total_errors for r in results)
    recipients = _get_admin_users()

    if results:
        platform_names = ', '.join(f'{r.platform.name}({r.status})' for r in results)
        title = f'每日余额同步完成 ({success_count}/{len(results)})'
        message = f'已完成 {len(results)} 个平台的余额同步:\n{platform_names}\n累计错误: {total_errors}'
        if total_errors == 0:
            SiteMessageUtil.notify_success(recipients, title, message)
        else:
            SiteMessageUtil.notify_info(recipients, title, message)

    logger.info(
        '每日余额同步完成: %d/%d 成功, 累计错误 %d',
        success_count,
        len(results),
        total_errors,
    )
    return {
        'synced': len(results),
        'success': success_count,
        'errors': total_errors,
    }
