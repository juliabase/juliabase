# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jb_common', '0002_remove_department_processes'),
        ('samples', '0002_external_operator_name_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdetails',
            name='show_users_from_departments',
            field=models.ManyToManyField(related_name='shown_users', verbose_name='show users from department', to='jb_common.Department', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='userdetails',
            name='show_users_from_department',
            field=models.ManyToManyField(related_name='shown_user', verbose_name='show users from department', to='jb_common.Department', blank=True),
            preserve_default=True,
        ),
    ]
