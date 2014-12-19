# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jb_common', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='app_label',
            field=models.CharField(default='institute', max_length=30, verbose_name='app label'),
            preserve_default=False,
        ),
    ]
