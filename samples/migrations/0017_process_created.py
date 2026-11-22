import jb_common.model_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0016_alter_process_last_modified_by_person'),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='created',
            field=jb_common.model_fields.DateTimeField(auto_now_add=True, null=True, verbose_name='created'),
        ),
    ]
