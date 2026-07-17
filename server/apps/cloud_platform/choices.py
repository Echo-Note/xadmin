"""云平台管理应用的枚举 choices 定义。"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class PlatformTypeChoices(models.TextChoices):
    """云平台类型枚举。"""

    TENCENT_CLOUD = 'tencent', _('腾讯云')
    ALI_CLOUD = 'aliyun', _('阿里云')
    AWS = 'aws', _('AWS')
    AZURE = 'azure', _('Azure')
    HUAWEI_CLOUD = 'huawei', _('华为云')
    VOLCENGINE = 'volcengine', _('火山引擎')
    VCENTER = 'vcenter', _('vCenter')
    MEICHENG = 'meicheng', _('美橙')
    OTHER = 'other', _('其他')


class CredentialTypeChoices(models.TextChoices):
    """凭据类型枚举。"""

    ACCESS_KEY = 'access_key', _('Access Key 密钥对')
    PASSWORD = 'password', _('用户名/密码')
    API_TOKEN = 'api_token', _('API Token')


class SyncStatusChoices(models.TextChoices):
    """同步状态枚举。"""

    PENDING = 'pending', _('等待中')
    RUNNING = 'running', _('运行中')
    SUCCESS = 'success', _('已完成')
    PARTIAL = 'partial', _('部分成功')
    FAILED = 'failed', _('失败')
    CANCELLED = 'cancelled', _('已取消')


class SyncResourceTypeChoices(models.TextChoices):
    """同步资源类型枚举。"""

    SERVER = 'server', _('云服务器')
    DOMAIN = 'domain', _('域名')
    DNS_RECORD = 'dns_record', _('DNS 解析记录')
    BALANCE = 'balance', _('账户余额')


class SyncTriggerTypeChoices(models.TextChoices):
    """同步触发类型枚举。"""

    MANUAL = 'manual', _('手动触发')
    SCHEDULED = 'scheduled', _('定时触发')
    WEBHOOK = 'webhook', _('Webhook 触发')


class AgentStatusChoices(models.TextChoices):
    """同步 Agent 状态枚举。"""

    PENDING = 'pending', _('等待中')
    RUNNING = 'running', _('运行中')
    SUCCESS = 'success', _('已完成')
    FAILED = 'failed', _('失败')
