#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


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
  a former version of the deployment at IEK-5/FZJ, this signal is used for
  triggering sychronisation of both nodes.
"""

import datetime
from django.db.models import signals
import django.utils.timezone
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

    :param sender: the sender of the signal; will always be the ``User`` model
    :param instance: the newly-added user
    :param created: whether the user was newly created.

    :type sender: model class
    :type instance: django.contrib.auth.models.User
    :type created: bool
    """
    if created:
        departments = models.Department.objects.all()
        department = departments[0] if departments.count() == 1 else None
        models.UserDetails.objects.create(user=instance, department=department)


@receiver(signals.post_migrate)
def add_all_user_details(**kwargs):
    """Create :py:class:`jb_common.models.UserDetails` for all users where
    necessary.  This is needed because during data migrations, no signals are
    sent.
    """
    for user in User.objects.filter(jb_user_details=None):
        add_user_details(User, user, created=True)


@receiver(maintain)
def expire_error_pages(sender, **kwargs):
    """Deletes all error pages which are older than six weeks.
    """
    now = django.utils.timezone.now()
    six_weeks_ago = now - datetime.timedelta(weeks=6)
    for error_page in models.ErrorPage.objects.filter(timestamp__lt=six_weeks_ago):
        error_page.delete()
