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


u"""Module for hooks into the ``User`` model.  They assure that every time a
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

from __future__ import absolute_import

import datetime
import django.contrib.auth.models
from django.db.models import signals as django_signals
from . import models as chantal_app
from .signals import maintain


def add_user_details(sender, instance, created=True, **kwargs):
    u"""Adds a `models.UserDetails` instance for every newly-created Django
    user.  However, you can also call it for existing users (``management.py``
    does it) because this function is idempotent.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``User`` model
      - `instance`: the newly-added user
      - `created`: whether the user was newly created.

    :type sender: model class
    :type instance: ``django.contrib.auth.models.User``
    :type created: bool
    """
    if created:
        chantal_app.UserDetails.objects.get_or_create(user=instance)

# It must be "post_save", otherwise, the ID may be ``None``.
django_signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)


def expire_error_pages(sender, **kwargs):
    u"""Deletes all error pages which are older than six weeks.
    """
    now = datetime.datetime.now()
    six_weeks_ago = now - datetime.timedelta(weeks=6)
    for error_page in chantal_app.ErrorPage.objects.filter(timestamp__lt=six_weeks_ago):
        error_page.delete()

maintain.connect(expire_error_pages, sender=None)
