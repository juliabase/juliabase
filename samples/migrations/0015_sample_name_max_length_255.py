import jb_common.model_fields
from django.db import migrations, models


# The limit was first 255 characters and then lowered to 63 before this was
# merged.  The name of this migration stays because Chantal applied it already.

class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0012_alter_feeddeletedsample_sample_name_and_more'),
        ('samples', '0014_merge_20261108_1825'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sample',
            name='name',
            field=jb_common.model_fields.CharField(db_index=True, max_length=63, unique=True, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='feeddeletedsample',
            name='sample_name',
            field=models.CharField(max_length=63, verbose_name='sample name'),
        ),
    ]
