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


"""Module for providing the JuliaBase signals.

:ivar maintain: This is sent in regular time intervals (e.g., every night), so
  that various subsystems can use it for maintenance work.  You can use this
  signal in your code like this::

      from jb_common.signals import maintain
      from django.dispatch import receiver

      @receiver(maintain)
      def my_handler(sender, **kwargs):
          ...


:ivar storage_changed: This is sent if the files on harddisk were changed.  In
  the reference deployment at IEK-5, this signal is used for triggering
  sychronisation of both nodes.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from django.db.models import signals
from django.dispatch import receiver
import django.dispatch
from django.contrib.auth.models import User
from jb_common import models


maintain = django.dispatch.Signal()

storage_changed = django.dispatch.Signal()


@receiver(signals.post_save, sender=User)
def add_user_details(sender, instance, created=True, **kwargs):
    """Adds a `models.UserDetails` instance for every newly-created Django user.

    If there is only one department, this is default for new users.  Otherwise,
    no department is set here.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``User`` model
      - `instance`: the newly-added user
      - `created`: whether the user was newly created.

    :type sender: model class
    :type instance: ``django.contrib.auth.models.User``
    :type created: bool
    """
    if created:
        departments = models.Department.objects.all()
        department = departments[0] if departments.count() == 1 else None
        models.UserDetails.objects.create(user=instance, department=department)


@receiver(signals.post_migrate)
def add_all_user_details(**kwargs):
    """Create ``UserDetails`` for all users where necessary.  This is needed
    because during data migrations, no signals are sent.
    """
    for user in User.objects.filter(jb_user_details=None):
        add_user_details(User, user, created=True)


@receiver(maintain)
def expire_error_pages(sender, **kwargs):
    """Deletes all error pages which are older than six weeks.
    """
    now = datetime.datetime.now()
    six_weeks_ago = now - datetime.timedelta(weeks=6)
    for error_page in models.ErrorPage.objects.filter(timestamp__lt=six_weeks_ago):
        error_page.delete()
