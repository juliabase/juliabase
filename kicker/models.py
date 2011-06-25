#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal-Kicker
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from django.db import models
import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _


class Match(models.Model):
    player_a_1 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"player 1 of team A"),
                                   related_name="match_player_a_1")
    player_a_2 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"player 2 of team A"),
                                   related_name="match_player_a_2")
    player_b_1 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"player 1 of team B"),
                                   related_name="match_player_b_1")
    player_b_2 = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"player 2 of team B"),
                                   related_name="match_player_b_2")
    goals_a = models.PositiveSmallIntegerField(_("goals of team A"))
    goals_b = models.PositiveSmallIntegerField(_("goals of team B"))
    seconds = models.FloatField(_("seconds"), help_text=_(u"duration of the match"))
    timestamp = models.DateTimeField(_(u"timestamp"))
    finished = models.BooleanField(_(u"finished"), default=False)
    reporter = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"reporter"), related_name="+")

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"match")
        verbose_name_plural = _(u"matches")


class Shares(models.Model):
    owner = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"owner"), related_name="bought_shares")
    bought_person = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"bought person"),
                                      related_name="sold_shares")
    number = models.PositiveSmallIntegerField(_("number of shares"))
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _(u"shares")
        verbose_name_plural = _(u"shareses")


class KickerNumber(models.Model):
    player = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"player"), related_name="kicker_numbers")
    number = models.FloatField(_("kicker number"))
    timestamp = models.DateTimeField(_(u"timestamp"))

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"kicker number")
        verbose_name_plural = _(u"kicker numbers")


class StockValue(models.Model):
    gambler = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"gambler"), related_name="stock_values")
    value = models.FloatField(_("stock value"))
    timestamp = models.DateTimeField(_(u"timestamp"))

    class Meta:
        ordering = ["timestamp"]
        verbose_name = _(u"stock value")
        verbose_name_plural = _(u"stock values")


class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"),
                                related_name="kicker_user_details")
    nickname = models.CharField(_(u"nickname"), max_length=30, blank=True)
    shortkey = models.CharField(_(u"shortkey"), max_length=1, blank=True)

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")

    def __unicode__(self):
        return unicode(self.user)
