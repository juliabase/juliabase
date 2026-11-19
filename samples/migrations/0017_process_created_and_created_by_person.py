import django.db.models.deletion
import jb_common.model_fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0016_alter_process_last_modified_by_person'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='created',
            field=jb_common.model_fields.DateTimeField(auto_now_add=True, null=True, verbose_name='created'),
        ),
        migrations.AddField(
            model_name='process',
            name='created_by_person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_processes', to=settings.AUTH_USER_MODEL, verbose_name='creator'),
        ),
    ]
