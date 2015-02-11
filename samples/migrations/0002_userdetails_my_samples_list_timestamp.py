# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='my_samples_list_timestamp',
            field=models.DateTimeField(default=datetime.datetime.now(), verbose_name='My Samples list last modified', auto_now_add=True),
            preserve_default=False,
        ),
    ]
