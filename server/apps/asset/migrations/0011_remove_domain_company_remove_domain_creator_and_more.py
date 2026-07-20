"""将域名相关模型（Domain/Filing/SslCertificate/DnsRecord）从 asset app 迁移状态中移除。

数据库层面不执行任何操作（表由 domain app 接管，db_table 保持 asset_* 原表名不变），
仅更新迁移状态：从 asset app 的模型注册表中删除域名相关模型。
配合 domain app 的 0001_initial 共同完成 app 拆分。
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('asset', '0010_dnsrecord_is_ssl_enabled_and_more'),
        ('domain', '0001_initial'),
    ]

    operations = [
        # 使用 SeparateDatabaseAndState：仅在迁移状态中删除模型，
        # 数据库层面不执行任何操作（表名保持不变，由 domain app 接管管理）。
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='domain',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='domain',
                    name='creator',
                ),
                migrations.RemoveField(
                    model_name='domain',
                    name='dept_belong',
                ),
                migrations.RemoveField(
                    model_name='domain',
                    name='modifier',
                ),
                migrations.RemoveField(
                    model_name='domain',
                    name='platform',
                ),
                migrations.RemoveField(
                    model_name='domain',
                    name='ssl_certificate',
                ),
                migrations.RemoveField(
                    model_name='filing',
                    name='domain',
                ),
                migrations.RemoveField(
                    model_name='filing',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='filing',
                    name='creator',
                ),
                migrations.RemoveField(
                    model_name='filing',
                    name='dept_belong',
                ),
                migrations.RemoveField(
                    model_name='filing',
                    name='modifier',
                ),
                migrations.RemoveField(
                    model_name='sslcertificate',
                    name='creator',
                ),
                migrations.RemoveField(
                    model_name='sslcertificate',
                    name='dept_belong',
                ),
                migrations.RemoveField(
                    model_name='sslcertificate',
                    name='modifier',
                ),
                migrations.DeleteModel(
                    name='DnsRecord',
                ),
                migrations.DeleteModel(
                    name='Domain',
                ),
                migrations.DeleteModel(
                    name='Filing',
                ),
                migrations.DeleteModel(
                    name='SslCertificate',
                ),
            ],
        ),
    ]
