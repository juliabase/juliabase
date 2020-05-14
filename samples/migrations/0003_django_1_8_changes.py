from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0002_userdetails_my_samples_list_timestamp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clearance',
            name='last_modified',
            field=models.DateTimeField(auto_now=True, verbose_name='last modified'),
        ),
        migrations.AlterField(
            model_name='externaloperator',
            name='alternative_email',
            field=models.EmailField(max_length=254, verbose_name='alternative email', blank=True),
        ),
        migrations.AlterField(
            model_name='externaloperator',
            name='email',
            field=models.EmailField(max_length=254, verbose_name='email'),
        ),
        migrations.AlterField(
            model_name='process',
            name='last_modified',
            field=models.DateTimeField(auto_now=True, verbose_name='last modified'),
        ),
        migrations.AlterField(
            model_name='sample',
            name='last_modified',
            field=models.DateTimeField(auto_now=True, verbose_name='last modified'),
        ),
        migrations.AlterField(
            model_name='sampleseries',
            name='last_modified',
            field=models.DateTimeField(auto_now=True, verbose_name='last modified'),
        ),
        migrations.AlterField(
            model_name='task',
            name='last_modified',
            field=models.DateTimeField(help_text='YYYY-MM-DD HH:MM:SS', verbose_name='last modified', auto_now=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='operator',
            field=models.ForeignKey(related_name='operated_tasks', verbose_name='operator', blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
        ),
    ]
