# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='externaloperator',
            name='name',
            field=models.CharField(unique=True, max_length=30, verbose_name='name'),
        ),
    ]
