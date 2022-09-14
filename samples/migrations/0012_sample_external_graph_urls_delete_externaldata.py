# Generated by Django 4.0.5 on 2022-09-14 09:00

from django.db import migrations
import jb_common.model_fields
import samples.models.common


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0011_graph_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='sample',
            name='external_graph_urls',
            field=jb_common.model_fields.JSONField(blank=True, default=samples.models.common.empty_list, verbose_name='external graph URLs'),
        ),
        migrations.DeleteModel(
            name='ExternalData',
        ),
    ]
