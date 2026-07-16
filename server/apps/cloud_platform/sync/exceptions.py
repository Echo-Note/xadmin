"""同步模块自定义异常。

定义同步流程中各类异常，便于上层统一捕获和处理。
"""

from __future__ import annotations


class SyncError(Exception):
    """同步模块基础异常，所有同步相关异常由此派生。"""

    def __init__(self, message: str = '', *, resource_type: str = '', detail: dict | None = None) -> None:
        """初始化同步异常。

        Args:
            message: 错误描述。
            resource_type: 关联的资源类型（server/domain/dns_record/balance）。
            detail: 错误详情字典，可包含平台名、实例ID等上下文。
        """
        super().__init__(message)
        self.resource_type = resource_type
        self.detail = detail or {}

    def as_error_dict(self, item: str = '') -> dict:
        """将异常转换为 SyncResult 兼容的错误字典。

        Args:
            item: 出错项标识（如服务器名称、域名）。

        Returns:
            {'item': ..., 'error': ..., 'detail': ...} 字典。
        """
        d: dict = {'item': item, 'error': str(self)}
        if self.detail:
            d['detail'] = self.detail
        return d


class CredentialNotFoundError(SyncError):
    """凭据缺失异常 — 指定平台无有效凭据时抛出。"""


class CredentialInvalidError(SyncError):
    """凭据无效异常 — 凭据已过期或格式错误时抛出。"""


class ApiRequestError(SyncError):
    """API 请求异常 — 云平台 API 调用失败时抛出。"""


class DataValidationError(SyncError):
    """数据校验异常 — Pydantic 校验或序列化器校验失败时抛出。"""


class DataWriteError(SyncError):
    """数据写入异常 — 数据库写入失败时抛出。"""


class PlatformNotSupportedError(SyncError):
    """平台不支持异常 — 指定功能该平台不支持时抛出。"""


class AgentExecutionError(SyncError):
    """Agent 执行异常 — Agent 子任务执行过程中的通用错误。"""


class SerializerError(SyncError):
    """序列化器操作异常 — Serializer 层 upsert 或查询失败时抛出。"""
