# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0004_copy_data_from_show_users_from_department_to_show_users_from_departments'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userdetails',
            name='show_users_from_department',
        ),
    ]
