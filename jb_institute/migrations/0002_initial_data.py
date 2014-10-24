# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def populate_with_initial_data(apps, schema_editor):
    User = apps.get_model("auth", "User")
    nobody = User.objects.create(username="nobody", last_name="Nobody")
    julia = User.objects.create(username="juliabase",
                                # Password is "12345".
                                password="pbkdf2_sha256$10000$6M4wIDbKNyiU$wxknFDlWqv13JtZ2M/MokIhiR/Bcj6IQLBUiJdpGWdU=",
                                first_name="Julia",
                                is_superuser=True, is_staff=True)

    Department = apps.get_model("jb_common", "Department")
    generic_institute = Department.objects.create(name="Generic Institute")

    Topic = apps.get_model("jb_common", "Topic")
    Topic.objects.create(name="Legacy", manager=nobody, department=generic_institute)

    Initials = apps.get_model("samples", "Initials")
    Initials.objects.create(initials="LGCY", user=nobody)


class Migration(migrations.Migration):

    dependencies = [
        ('jb_institute', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_with_initial_data),
    ]
