#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""Module for hooks into the ``User`` model.  They assure that every time a
user is added, ``UserDetails`` are added.
"""

from __future__ import absolute_import

import django.contrib.auth.models
from django.db.models import signals
from . import models as chantal_app


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
signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)
