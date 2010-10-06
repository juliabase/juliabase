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
    timestamp = models.DateTimeField(_(u"timestamp"))

    class Meta:
        verbose_name = _(u"Match")
        verbose_name_plural = _(u"Matches")


class Shares(models.Model):
    owner = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"owner"), related_name="bought shares")
    bought_person = models.ForeignKey(django.contrib.auth.models.User, verbose_name=_(u"bought person"),
                                      related_name="sold shares")
    number = models.PositiveSmallIntegerField(_("number of shares"))
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _(u"Shares")
        verbose_name_plural = _(u"Shareses")


class PlotPointsSet(models.Model):
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)
    kicker_numbers = models.TextField(_("kicker numbers"), blank=True, help_text=_(u"in JSON format"))
    stock_values = models.TextField(_("stock values"), blank=True, help_text=_(u"in JSON format"))

    class Meta:
        verbose_name = _(u"Plot points set")
        verbose_name_plural = _(u"Plot points sets")


class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"),
                                related_name="kicker_user_details")
    kicker_number = models.FloatField(_("kicker number"), null=True, blank=True)
    stock_value = models.FloatField(_("stock value"), null=True, blank=True)
    number_of_matches = models.PositiveIntegerField(_("number of matches"), default=0)

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")

    def __unicode__(self):
        return unicode(self.user)
