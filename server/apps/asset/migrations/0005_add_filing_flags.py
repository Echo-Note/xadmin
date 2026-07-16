"""添加 ICP/公安备案标记字段（已应用于数据库但迁移文件缺失）。

此迁移仅恢复迁移图谱一致性，对应字段后已从模型中删除，
下一步 makemigrations 会自动生成删除迁移。
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asset', '0004_add_domain_contacts'),
    ]

    operations = [
        migrations.AddField(
            model_name='domain',
            name='is_icp_filed',
            field=models.BooleanField(default=False, verbose_name='ICP已备案'),
        ),
        migrations.AddField(
            model_name='domain',
            name='is_ps_filed',
            field=models.BooleanField(default=False, verbose_name='公安已备案'),
        ),
    ]
