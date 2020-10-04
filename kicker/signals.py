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


import datetime
from django.db.models import signals
import django.utils.timezone
from django.dispatch import receiver
from django.contrib.auth.models import User
from jb_common.signals import maintain
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


@receiver(maintain)
def expire_shortkeys(sender, **kwargs):
    one_year_ago = django.utils.timezone.now() - datetime.timedelta(356)
    for details in kicker_app.UserDetails.objects.exclude(shortkey=""):
        try:
            too_old = kicker_app.KickerNumber.objects.filter(player=details.user).latest().timestamp < one_year_ago
        except kicker_app.KickerNumber.DoesNotExist:
            too_old = False
        if too_old or not details.user.is_active:
            details.shortkey = ""
            details.save()

@receiver(maintain)
def expire_matches(sender, **kwargs):
    one_day_ago = django.utils.timezone.now() - datetime.timedelta(1)
    kicker_app.Match.objects.filter(finished=False, timestamp__lt=one_day_ago).delete()
