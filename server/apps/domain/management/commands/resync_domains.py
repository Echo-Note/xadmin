"""清空域名管理应用所有表并完整重新同步。

清空 4 张表（DnsRecord / Filing / SslCertificate / Domain），
随后对所有支持域名同步的活跃云平台执行完整重新同步。

同步流程（SyncEngine 自动编排）：
  Phase 1: 域名同步（domain）
  Phase 2: DNS 解析记录同步（dns_record，平台支持时）
  Phase 3: 域名后处理（domain_post，自动触发）
    - 有 www DNS 记录的域名 → 创建 Filing 备案记录 + 检测 SSL 证书
    - 无 www DNS 记录的域名 → 不创建/删除 Filing 备案记录

Usage:
    uv run python manage.py resync_domains              # 清空 + 重新同步
    uv run python manage.py resync_domains --clear-only  # 仅清空不同步
    uv run python manage.py resync_domains --sync-only   # 仅同步不清空
"""

import logging

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from apps.domain.models import DnsRecord, Domain, Filing, SslCertificate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """清空域名表并重新同步。"""

    help = (
        '清空域名管理应用所有表（DnsRecord/Filing/SslCertificate/Domain）'
        '并完整重新同步（域名→DNS记录→SSL检测+Filing联动）'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """添加命令行参数。"""
        parser.add_argument(
            '--clear-only',
            action='store_true',
            default=False,
            help='仅清空表数据，不执行重新同步',
        )
        parser.add_argument(
            '--sync-only',
            action='store_true',
            default=False,
            help='仅执行重新同步，不清空表数据',
        )

    def handle(self, *args, **options) -> None:
        """执行清空 + 重新同步流程。"""
        clear_only = options.get('clear_only', False)
        sync_only = options.get('sync_only', False)

        if clear_only and sync_only:
            self.stdout.write(self.style.ERROR('--clear-only 与 --sync-only 不可同时使用'))
            return

        # ---- Step 1: 清空表 ----
        if not sync_only:
            self._clear_tables()

        # ---- Step 2: 重新同步 ----
        if not clear_only:
            self._resync()

        self.stdout.write(self.style.SUCCESS('域名重新同步流程完成。'))

    # ------------------------------------------------------------------
    # 清空表
    # ------------------------------------------------------------------

    def _clear_tables(self) -> None:
        """按 FK 依赖顺序清空 4 张表。

        删除顺序：
        1. DnsRecord（FK→Domain CASCADE）
        2. Filing（OneToOne→Domain CASCADE）
        3. Domain（FK→SslCertificate SET_NULL）
        4. SslCertificate

        使用事务保证原子性，任一步失败则全部回滚。
        """
        self.stdout.write(self.style.WARNING('开始清空域名管理应用所有表...'))

        with transaction.atomic():
            dns_count, _ = DnsRecord.objects.all().delete()
            filing_count, _ = Filing.objects.all().delete()
            domain_count, _ = Domain.objects.all().delete()
            ssl_count, _ = SslCertificate.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'已清空: DnsRecord={dns_count}, Filing={filing_count}, '
                f'Domain={domain_count}, SslCertificate={ssl_count}'
            )
        )

    # ------------------------------------------------------------------
    # 重新同步
    # ------------------------------------------------------------------

    def _resync(self) -> None:
        """对所有支持域名同步的活跃云平台执行完整重新同步。

        遍历所有 is_active=True 的云平台，通过同步器注册表判断是否支持
        domain 资源同步。对支持的平台以同步方式执行 SyncEngine，
        resources 包含 domain 及 dns_record（若平台支持）。

        SyncEngine 会自动在 domain 同步后追加 domain_post 阶段：
        - 有 www DNS 记录的域名 → 创建 Filing + 检测 SSL 证书
        - 无 www DNS 记录的域名 → 不创建/删除 Filing
        """
        from apps.cloud_platform.models import CloudPlatform
        from apps.cloud_platform.sync import SyncEngine, _ensure_platforms_loaded
        from apps.cloud_platform.sync.registry import get_syncer

        _ensure_platforms_loaded()

        platforms = CloudPlatform.objects.filter(is_active=True)
        if not platforms.exists():
            self.stdout.write(self.style.WARNING('无活跃云平台，跳过同步'))
            return

        total_platforms = 0
        total_created = 0
        total_updated = 0
        total_errors = 0

        for platform in platforms:
            syncer_cls = get_syncer(platform.platform_type)
            if syncer_cls is None:
                self.stdout.write(self.style.WARNING(f'[{platform.name}] 未找到同步器，跳过'))
                continue

            supported = syncer_cls.SUPPORTED_RESOURCES
            if 'domain' not in supported:
                self.stdout.write(
                    self.style.WARNING(f'[{platform.name}] 平台类型 {platform.platform_type} 不支持域名同步，跳过')
                )
                continue

            # 确定资源列表：domain 必选，dns_record 可选
            resources = ['domain']
            if 'dns_record' in supported:
                resources.append('dns_record')

            total_platforms += 1
            self.stdout.write(
                self.style.HTTP_INFO(f'开始同步 [{platform.name}] ({platform.platform_type}) resources={resources} ...')
            )

            try:
                engine = SyncEngine()
                record = engine.run(platform, sync_type='manual', resources=resources)
            except Exception as e:
                logger.exception('同步 [%s] 异常', platform.name)
                self.stdout.write(self.style.ERROR(f'[{platform.name}] 同步异常: {e}'))
                total_errors += 1
                continue

            total_created += record.total_created
            total_updated += record.total_updated
            total_errors += record.total_errors

            self.stdout.write(
                self.style.SUCCESS(
                    f'[{platform.name}] 同步完成: status={record.status} '
                    f'新建={record.total_created} 更新={record.total_updated} '
                    f'错误={record.total_errors}'
                )
            )

            # 检查 domain_post agent 是否派发了 ICP 预检测
            from apps.cloud_platform.models import SyncAgentLog

            post_agent = SyncAgentLog.objects.filter(sync_record=record, resource_type='domain_post').first()
            if post_agent and post_agent.extra_data:
                precheck_info = post_agent.extra_data.get('precheck', {})
                if precheck_info.get('dispatched'):
                    self.stdout.write(
                        self.style.HTTP_INFO(
                            f'  → ICP 预检测已异步派发: task_id={precheck_info.get("task_id", "?")}, '
                            f'待检测={precheck_info.get("total", 0)} 条（Celery worker 执行）'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n重新同步汇总: 平台数={total_platforms} '
                f'新建={total_created} 更新={total_updated} 错误={total_errors}'
            )
        )
