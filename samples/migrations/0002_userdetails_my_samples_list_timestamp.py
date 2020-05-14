from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='my_samples_list_timestamp',
            field=models.DateTimeField(default=django.utils.timezone.now(), verbose_name='My Samples list last modified', auto_now_add=True),
            preserve_default=False,
        ),
    ]
