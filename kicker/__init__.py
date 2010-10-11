#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from __future__ import absolute_import

from django.db.models import signals
import django.contrib.auth.models
from . import models as kicker_app
from chantal_common.maintenance import maintain


def add_user_details(sender, instance, created, **kwargs):
    u"""Create ``UserDetails`` for every newly created user.
    """
    if created:
        kicker_app.UserDetails.objects.get_or_create(user=instance)

signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)


def create_user_details(sender, **kwargs):
    for user in django.contrib.auth.models.User.objects.all():
        kicker_app.UserDetails.objects.get_or_create(user=user)

maintain.connect(create_user_details, sender=None)
