#!/usr/bin/env python
"""同步模块集成测试脚本。

用法:
    cd server && uv run python tests/test_sync.py [--platform tencent|aliyun|meicheng|vsphere|all]

依赖:
    uv pip install python-dotenv
"""

import os
import sys
import time
from pathlib import Path

# --- 0. 环境设置 ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')

# 加载 .django-test-env
try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parents[2] / '.django-test-env'
    load_dotenv(env_file, override=True)
    print(f'[OK] 加载环境配置: {env_file}')
except ImportError:
    print('[WARN] python-dotenv 未安装，使用当前环境变量')
except FileNotFoundError:
    print('[WARN] .django-test-env 文件不存在，使用当前环境变量')

import django

django.setup()

from apps.cloud_platform.choices import CredentialTypeChoices, PlatformTypeChoices  # noqa: E402
from apps.cloud_platform.models import CloudPlatform, Credential, SyncAgentLog, SyncRecord  # noqa: E402
from apps.cloud_platform.sync.engine import SyncEngine  # noqa: E402

# --- 1. 平台与凭据配置 ---

PLATFORM_CONFIGS = {
    'tencent': {
        'name': '腾讯云-测试',
        'platform_type': PlatformTypeChoices.TENCENT_CLOUD,
        'region': 'ap-guangzhou',
        'credentials': [
            {
                'credential_name': 'API密钥',
                'credential_type': CredentialTypeChoices.ACCESS_KEY,
                'access_key': os.getenv('TENCENT_ENV_SECRET_ID', ''),
                'access_secret': os.getenv('TENCENT_ENV_SECRET_KEY', ''),
            }
        ],
        'resources': ['server', 'domain', 'dns_record', 'balance'],
    },
    'aliyun': {
        'name': '阿里云-测试',
        'platform_type': PlatformTypeChoices.ALI_CLOUD,
        'region': 'cn-hangzhou',
        'credentials': [
            {
                'credential_name': 'API密钥',
                'credential_type': CredentialTypeChoices.ACCESS_KEY,
                'access_key': os.getenv('ALIYUN_ENV_SECRET_ID', ''),
                'access_secret': os.getenv('ALIYUN_ENV_SECRET_KEY', ''),
            }
        ],
        'resources': ['server', 'domain', 'balance'],
    },
    'meicheng': {
        'name': '美橙-测试',
        'platform_type': PlatformTypeChoices.MEICHENG,
        'region': '',
        'credentials': [
            {
                'credential_name': 'API认证',
                'credential_type': CredentialTypeChoices.PASSWORD,
                'username': os.getenv('MEICONG_ENV_USERNAME', ''),
                'password': os.getenv('MEICONG_ENV_PASSWORD', ''),
                'email': os.getenv('MEICONG_ENV_EMAIL', ''),
            }
        ],
        'resources': ['domain', 'dns_record', 'balance'],
    },
    'vsphere': {
        'name': 'vSphere-测试',
        'platform_type': PlatformTypeChoices.VCENTER,
        'region': '',
        'endpoint': os.getenv('VCENTER_HOST', ''),
        'credentials': [
            {
                'credential_name': '管理员',
                'credential_type': CredentialTypeChoices.PASSWORD,
                'username': os.getenv('vcenter_username', ''),
                'password': os.getenv('VCENTER_PASSWORD', ''),
            }
        ],
        'resources': ['server'],
    },
}


def setup_platform(pid: str) -> CloudPlatform:
    """创建或更新云平台实例及凭据。"""
    cfg = PLATFORM_CONFIGS[pid]

    # 1. 查找或创建平台
    platform, p_created = CloudPlatform.objects.get_or_create(
        name=cfg['name'],
        defaults={
            'platform_type': cfg['platform_type'],
            'region': cfg['region'],
            'endpoint': cfg.get('endpoint', ''),
            'is_active': True,
        },
    )
    action = '创建' if p_created else '复用'
    print(f'  [{action}] 平台: {platform.name} (pk={str(platform.pk)[:8]}...) type={platform.platform_type}')

    # 2. 添加凭据
    for cred_cfg in cfg['credentials']:
        Credential.objects.update_or_create(
            platform=platform,
            credential_name=cred_cfg['credential_name'],
            defaults={
                'credential_type': cred_cfg['credential_type'],
                'access_key': cred_cfg.get('access_key', ''),
                'access_secret': cred_cfg.get('access_secret', ''),
                'username': cred_cfg.get('username', ''),
                'password': cred_cfg.get('password', ''),
                'email': cred_cfg.get('email', ''),
            },
        )
        print(f'  [OK] 凭据: {cred_cfg["credential_name"]}')

    return platform


def run_sync(platform: CloudPlatform, resources: list[str]) -> SyncRecord | None:
    """执行同步并返回记录。"""
    engine = SyncEngine()
    t0 = time.time()
    try:
        sync_record = engine.run(platform, sync_type='manual', resources=resources)
        elapsed = time.time() - t0
        print(f'  [{sync_record.status}] 同步完成 ({elapsed:.1f}s)')
        print(
            f'    新建={sync_record.total_created} 更新={sync_record.total_updated} '
            f'终止={sync_record.total_terminated} 错误={sync_record.total_errors}'
        )

        if sync_record.total_errors > 0:
            for err in (sync_record.error_detail or [])[:5]:
                print(f'    [ERR] {err["item"]}: {err["error"][:80]}')

        # 打印 Agent 级别日志
        agents = SyncAgentLog.objects.filter(sync_record=sync_record)
        for agent in agents:
            print(
                f'    Agent [{agent.agent_name}] {agent.status}: '
                f'c={agent.created_count} u={agent.updated_count} '
                f't={agent.terminated_count} e={agent.error_count}'
            )

        return sync_record
    except Exception as e:
        elapsed = time.time() - t0
        print(f'  [FAIL] 同步异常 ({elapsed:.1f}s): {e}')
        return None


# --- 2. 主流程 ---

if __name__ == '__main__':
    target = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == '--platform' else 'all'

    if target == 'all':
        platforms_to_test = list(PLATFORM_CONFIGS.keys())
    elif target in PLATFORM_CONFIGS:
        platforms_to_test = [target]
    else:
        print(f'未知平台: {target}，可选: {list(PLATFORM_CONFIGS.keys())}')
        sys.exit(1)

    print(f'\n{"=" * 60}')
    print(f'同步测试 — 目标平台: {platforms_to_test}')
    print(f'{"=" * 60}')

    summary = []
    for pid in platforms_to_test:
        print(f'\n--- {pid} ---')
        platform = setup_platform(pid)
        record = run_sync(platform, PLATFORM_CONFIGS[pid]['resources'])
        if record:
            summary.append(
                f'{pid:12s} | {record.status:8s} | '
                f'新增:{record.total_created:>4d} 更新:{record.total_updated:>4d} '
                f'错误:{record.total_errors:>3d}'
            )
        else:
            summary.append(f'{pid:12s} | FAIL')

    print(f'\n{"=" * 60}')
    print('汇总结果')
    print(f'{"=" * 60}')
    for line in summary:
        print(f'  {line}')
    print()
