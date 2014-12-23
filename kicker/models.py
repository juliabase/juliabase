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


from __future__ import absolute_import, unicode_literals
import django.utils.six as six
from django.utils.encoding import python_2_unicode_compatible

from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _


class Match(models.Model):
    player_a_1 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("player 1 of team A"),
                                   related_name="match_player_a_1")
    player_a_2 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("player 2 of team A"),
                                   related_name="match_player_a_2")
    player_b_1 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("player 1 of team B"),
                                   related_name="match_player_b_1")
    player_b_2 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("player 2 of team B"),
                                   related_name="match_player_b_2")
    goals_a = models.PositiveSmallIntegerField(_("goals of team A"))
    goals_b = models.PositiveSmallIntegerField(_("goals of team B"))
    seconds = models.FloatField(_("seconds"), help_text=_("duration of the match"))
    timestamp = models.DateTimeField(_("timestamp"))
    finished = models.BooleanField(_("finished"), default=False)
    reporter = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("reporter"), related_name="+")

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _("match")
        verbose_name_plural = _("matches")


class Shares(models.Model):
    owner = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("owner"), related_name="bought_shares")
    bought_person = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("bought person"),
                                      related_name="sold_shares")
    number = models.PositiveSmallIntegerField(_("number of shares"))
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("shares")
        verbose_name_plural = _("shareses")


class KickerNumber(models.Model):
    player = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("player"), related_name="kicker_numbers")
    number = models.FloatField(_("kicker number"))
    timestamp = models.DateTimeField(_("timestamp"))

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _("kicker number")
        verbose_name_plural = _("kicker numbers")


class StockValue(models.Model):
    gambler = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_("gambler"), related_name="stock_values")
    value = models.FloatField(_("stock value"))
    timestamp = models.DateTimeField(_("timestamp"))

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _("stock value")
        verbose_name_plural = _("stock values")


@python_2_unicode_compatible
class UserDetails(models.Model):
    """Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_("user"),
                                related_name="kicker_user_details")
    nickname = models.CharField(_("nickname"), max_length=30, blank=True)
    shortkey = models.CharField(_("shortkey"), max_length=1, blank=True)

    class Meta:
        verbose_name = _("user details")
        verbose_name_plural = _("user details")

    def __str__(self):
        return six.text_type(self.user)
