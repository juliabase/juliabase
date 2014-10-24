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

from django.db.models import signals
import django.contrib.auth.models
from django.dispatch import receiver
from kicker import models as kicker_app
from jb_common.signals import maintain


@receiver(signals.post_save, sender=django.contrib.auth.models.User)
def add_user_details(sender, instance, created, **kwargs):
    u"""Create ``UserDetails`` for every newly created user.
    """
    if created:
        kicker_app.UserDetails.objects.create(user=instance)


@receiver(maintain)
def create_user_details(sender, **kwargs):
    for user in django.contrib.auth.models.User.objects.all():
        kicker_app.UserDetails.objects.get_or_create(user=user)

