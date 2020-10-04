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


from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext


class Match(models.Model):
    player_a_1 = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("player 1 of team A"),
                                   related_name="match_player_a_1")
    player_a_2 = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("player 2 of team A"),
                                   related_name="match_player_a_2")
    player_b_1 = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("player 1 of team B"),
                                   related_name="match_player_b_1")
    player_b_2 = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("player 2 of team B"),
                                   related_name="match_player_b_2")
    goals_a = models.PositiveSmallIntegerField(_("goals of team A"))
    goals_b = models.PositiveSmallIntegerField(_("goals of team B"))
    seconds = models.FloatField(_("seconds"), help_text=_("duration of the match"))
    timestamp = models.DateTimeField(_("timestamp"))
    finished = models.BooleanField(_("finished"), default=False)
    reporter = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("reporter"),
                                 related_name="+")

    class Meta:
        ordering = ["timestamp"]
        get_latest_by = "timestamp"
        verbose_name = _("match")
        verbose_name_plural = _("matches")


class Shares(models.Model):
    owner = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("owner"),
                              related_name="bought_shares")
    bought_person = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("bought person"),
                                      related_name="sold_shares")
    number = models.PositiveSmallIntegerField(_("number of shares"))
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]
        get_latest_by = "timestamp"
        verbose_name = _("shares")
        verbose_name_plural = _("shareses")


class KickerNumber(models.Model):
    player = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("player"),
                               related_name="kicker_numbers")
    number = models.FloatField(_("kicker number"))
    timestamp = models.DateTimeField(_("timestamp"))

    class Meta:
        ordering = ["timestamp"]
        get_latest_by = "timestamp"
        verbose_name = _("kicker number")
        verbose_name_plural = _("kicker numbers")


class StockValue(models.Model):
    gambler = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("gambler"),
                                related_name="stock_values")
    value = models.FloatField(_("stock value"))
    timestamp = models.DateTimeField(_("timestamp"))

    class Meta:
        ordering = ["timestamp"]
        get_latest_by = "timestamp"
        verbose_name = _("stock value")
        verbose_name_plural = _("stock values")


class UserDetails(models.Model):
    """Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, models.CASCADE, primary_key=True, verbose_name=_("user"),
                                related_name="kicker_user_details")
    nickname = models.CharField(_("nickname"), max_length=30, blank=True)
    shortkey = models.CharField(_("shortkey"), max_length=1, blank=True)

    class Meta:
        verbose_name = _("user details")
        verbose_name_plural = _("user details")

    def __str__(self):
        return str(self.user)


_ = ugettext
