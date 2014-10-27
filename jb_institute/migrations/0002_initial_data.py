#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

from __future__ import absolute_import, unicode_literals, division

from django.db import migrations


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
