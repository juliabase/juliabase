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
from django.dispatch import receiver
from django.contrib.auth.models import User
from kicker import models as kicker_app


@receiver(signals.post_save, sender=User)
def add_user_details(sender, instance, created, **kwargs):
    """Create ``UserDetails`` for every newly created user.
    """
    if created:
        kicker_app.UserDetails.objects.create(user=instance)


@receiver(signals.post_migrate)
def add_all_user_details(sender, **kwargs):
    """Create ``UserDetails`` for all users where necessary.  This is needed
    because during data migrations, no signals are sent.
    """
    for user in User.objects.filter(kicker_user_details=None):
        add_user_details(User, user, created=True)
