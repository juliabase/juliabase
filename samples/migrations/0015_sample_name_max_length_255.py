import jb_common.model_fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0014_merge_20261108_1825'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sample',
            name='name',
            field=jb_common.model_fields.CharField(db_index=True, max_length=255, unique=True, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='feeddeletedsample',
            name='sample_name',
            field=models.CharField(max_length=255, verbose_name='sample name'),
        ),
    ]
