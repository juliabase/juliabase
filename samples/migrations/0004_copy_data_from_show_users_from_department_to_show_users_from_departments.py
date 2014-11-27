# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def copy_data(apps, schema_editor):
    UserDetails = apps.get_model("samples", "UserDetails")
    for detail in UserDetails.objects.iterator():
        detail.show_users_from_departments = detail.show_users_from_department.all()
        detail.save()


def reverse_data_migration(apps, schema_editor):
    UserDetails = apps.get_model("samples", "UserDetails")
    for detail in UserDetails.objects.iterator():
        detail.show_users_from_department = detail.show_users_from_departments.all()
        detail.save()


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0003_create_show_users_from_departments'),
    ]

    operations = [
        migrations.RunPython(copy_data, reverse_data_migration),
    ]
