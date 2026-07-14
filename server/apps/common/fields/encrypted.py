"""AES 加密文本字段，数据库存储密文，应用层自动加解密。"""

from django.conf import settings
from django.db import models

from apps.common.base.utils import AESCipherV2


def _get_encryption_key() -> str:
    """获取加密密钥，以 SECRET_KEY 为种子派生。

    优先使用配置项 CLOUD_PLATFORM_ENCRYPTION_KEY，未配置时回退到 Django SECRET_KEY，
    确保更换密钥后历史数据仍可用之前的密钥解密。

    Returns:
        加密密钥字符串。
    """
    return getattr(settings, 'CLOUD_PLATFORM_ENCRYPTION_KEY', None) or settings.SECRET_KEY


class EncryptedTextField(models.TextField):
    """透明加解密文本字段。

    写入时自动使用 AES-256-CBC（OpenSSL Salted 格式）加密，
    读取时自动解密。对外表现为普通文本字段，对数据库存储为密文。

    用法示例::

        class MyModel(models.Model):
            secret = EncryptedTextField(verbose_name="密钥", blank=True, default="")

    注意事项:
        - 密文长度远大于明文，建议使用 TextField 而非 CharField。
        - 查询时不可直接对密文字段做 LIKE/icontains 等模糊匹配。
        - 更换 SECRET_KEY 后历史数据需做迁移处理。
    """

    description = "AES-256-CBC 加密文本字段，数据库存储密文"

    def get_prep_value(self, value: str | None) -> str | None:
        """写入数据库前加密。

        Args:
            value: 原始明文值。

        Returns:
            加密后的 Base64 密文字符串。
        """
        if value is None:
            return value
        if not isinstance(value, str):
            value = str(value)
        if value == "":
            return value
        return AESCipherV2(_get_encryption_key()).encrypt(value).decode('utf-8')

    def from_db_value(self, value: str | None, expression, connection) -> str | None:
        """从数据库读取时解密。

        Args:
            value: 数据库中的密文值。
            expression: SQL 表达式对象。
            connection: 数据库连接对象。

        Returns:
            解密后的明文字符串。
        """
        if value is None:
            return value
        if not isinstance(value, str) or value == "":
            return value
        try:
            return AESCipherV2(_get_encryption_key()).decrypt(value)
        except Exception:
            # 如果解密失败（如密钥已更换），返回原始值，避免数据丢失
            return value

    def to_python(self, value: str | None) -> str | None:
        """反序列化时解密（与 from_db_value 逻辑一致）。

        Args:
            value: 输入值。

        Returns:
            解密后的明文字符串。
        """
        if value is None:
            return value
        if not isinstance(value, str) or value == "":
            return value
        try:
            return AESCipherV2(_get_encryption_key()).decrypt(value)
        except Exception:
            return value
