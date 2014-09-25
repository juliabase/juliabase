#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Module for hooks into the ``User`` model.  They assure that every time a
user is added, ``UserDetails`` are added.

Additionally, there is a hook to purge too old error pages.

The error codes for a JSON client are the following:

    ======= ===============================================
    code    description
    ======= ===============================================
    1       Web form error
    2       URL not found, i.e. HTTP 404
    3       GET/POST parameter missing
    4       user could not be authenticated
    5       GET/POST parameter invalid
    ======= ===============================================
"""

from __future__ import absolute_import, unicode_literals

import datetime
import django.contrib.auth.models
from django.db.models import signals as django_signals
from django.dispatch import receiver
from jb_common import models as jb_app
from jb_common.signals import maintain


# It must be "post_save", otherwise, the ID may be ``None``.
@receiver(django_signals.post_save, sender=django.contrib.auth.models.User)
def add_user_details(sender, instance, created=True, **kwargs):
    """Adds a `models.UserDetails` instance for every newly-created Django
    user.  However, you can also call it for existing users (``management.py``
    does it) because this function is idempotent.

    If there is only one department, this is default for new users.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``User`` model
      - `instance`: the newly-added user
      - `created`: whether the user was newly created.

    :type sender: model class
    :type instance: ``django.contrib.auth.models.User``
    :type created: bool
    """
    if created:
        departments = jb_app.Department.objects.all()
        department = departments[0] if departments.count() == 1 else None
        jb_app.UserDetails.objects.get_or_create(user=instance, department=department)


@receiver(maintain)
def expire_error_pages(sender, **kwargs):
    """Deletes all error pages which are older than six weeks.
    """
    now = datetime.datetime.now()
    six_weeks_ago = now - datetime.timedelta(weeks=6)
    for error_page in jb_app.ErrorPage.objects.filter(timestamp__lt=six_weeks_ago):
        error_page.delete()
