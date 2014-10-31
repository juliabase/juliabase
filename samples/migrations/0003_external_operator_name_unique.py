# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jb_institute', '0002_initial_data'),
        ('samples', '0002_test_processes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='externaloperator',
            name='name',
            field=models.CharField(unique=True, max_length=30, verbose_name='name'),
        ),
    ]
