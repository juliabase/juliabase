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

from __future__ import divison, absolute_import

import datetime
from . import models
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from chantal_common.utils import respond_in_json, JSONRequestException
from samples.views import utils


class NoKickerNumber(Exception):
    pass


def get_current_kicker_number(player):
    try:
        return models.KickerNumber.objects.filter(player=player).latest("timestamp").number
    except models.KickerNumber.DoesNotExist:
        preliminary_kicker_number = 1500
        matches = models.Matches.objects.filter(Q(player_a_1=player) | Q(player_a_2=player) | Q(player_b_1=player) |
                                                Q(player_b_2=player)).distinct()
        # FixMe: This part is very inefficient.  One should collect the matches
        # *before* one enters the while loop.  This way, one avoids unnecessary
        # doubling of many operations.  On the other hand, one needs a new data
        # structure that holds the matches.
        cycles_left = 50
        while cycles_left:
            cycles_left -= 1
            old_start_number = preliminary_kicker_number
            number_of_matches = 0
            for match in matches:
                try:
                    number_player_a_1 = get_current_kicker_number(match.player_a_1) if match.player_a_1 != player \
                        else preliminary_kicker_number
                    number_player_a_2 = get_current_kicker_number(match.player_a_2) if match.player_a_2 != player \
                        else preliminary_kicker_number
                    number_player_b_1 = get_current_kicker_number(match.player_b_1) if match.player_b_1 != player \
                        else preliminary_kicker_number
                    number_player_b_2 = get_current_kicker_number(match.player_b_2) if match.player_b_2 != player \
                        else preliminary_kicker_number
                except NoKickerNumber:
                    continue
                S = 1/2 + 180/7 * (match.goals_a - match.goals_b) / seconds
                E = 1 / (1 + 10**((number_player_a_1 + number_player_a_2 - number_player_b_1 - number_player_b_2) / 800))
                delta = S - E
                delta_player = 40 * delta
                if player in [match.player_b_1, match.payer_b_2]:
                    delta_player = - delta_player
                preliminary_kicker_number += delta_player
                number_of_matches += 1
            if number_of_matches < 7:
                raise NoKickerNumber
            if old_start_number - preliminary_kicker_number < 1:
                break
        return preliminary_kicker_number


def get_k(player):
    return 32 if models.KickerNumber.objects.filter(player=player).count() > 30 else 40


def get_old_stock_value(player):
    try:
        return models.StockValue.objects.filter(gambler=player).latest("timestamp")
    except models.StockValue.DoesNotExist:
        return 100


@login_required
def edit_match(request, id_=None):
    match = get_object_or_404(models.Match, pk=utils.int_or_zero(id_)) if id_ else None
    try:
        if not match:
            player_a_1 = get_object_or_404(django.contrib.auth.models.User, username=request.POST["player_a_1"])
            player_a_2 = get_object_or_404(django.contrib.auth.models.User, username=request.POST["player_a_2"])
            player_b_1 = get_object_or_404(django.contrib.auth.models.User, username=request.POST["player_b_1"])
            player_b_2 = get_object_or_404(django.contrib.auth.models.User, username=request.POST["player_b_2"])
        goals_a = int(request.POST["goals_a"])
        goals_b = int(request.POST["goals_b"])
        seconds = float(request.POST["seconds"])
        finished = request.POST.get("finished") == "on"
        timestamp = datetime.datetime.strptime("%Y-%m-%d %H-%M-%S", request.POST["timestamp"])
    except KeyError as error:
        raise JSONRequestException(3, u"At least the datafield \"{0}\" was missing".format(error.args[0]))
    except ValueError as error:
        raise JSONRequestException(5, error.args[0])
    if seconds <= 0:
        raise JSONRequestException(5, u"Seconds must be positive")
    if not match:
        if player_a_1 == player_a_2 and player_b_1 != player_b_2 or player_a_1 != player_a_2 and player_b_1 == player_b_2:
            raise JSONRequestException(3000, "Games with three players can't be processed")
        if player_a_1 == player_a_2 == player_b_1 == player_b_2:
            raise JSONRequestException(3001, "All players are the same person")
        if models.Match.objects.filter(finished=False).exists():
            raise JSONRequestException(3004, "You can't add a match if another is not yet finished")
    else:
        if match.finished:
            raise JSONRequestException(3003, "A finished match can't be edited anymore")
        player_a_1 = match.player_a_1
        player_a_2 = match.player_a_2
        player_b_1 = match.player_b_1
        player_b_2 = match.player_b_2
    try:
        if models.Match.objects.latest("timestamp").timestamp >= timestamp:
            raise JSONRequestException(3002, "This game is not the most recent one")
    except models.Match.DoesNotExist:
        pass
    if match:
        match.player_a_1 = player_a_1
        match.player_a_2 = player_a_2
        match.player_b_1 = player_b_1
        match.player_b_2 = player_b_2
        match.goals_a = goals_a
        match.goals_b = goals_b
        match.timestamp = timestamp
        match.finished = finished
        match.seconds = seconds
        match.save()
    else:
        match = models.Match.objects.create(
            player_a_1=player_a_1, player_a_2=player_a_2, player_b_1=player_b_1, player_b_2=player_b_2,
            goals_a=goals_a, goals_b=goals_b, timestamp=timestamp, finished=finished, seconds=seconds)
    if match.finished:
        now = datetime.datetime.now()
        try:
            number_player_a_1 = get_current_kicker_number(player_a_1)
            number_player_a_2 = get_current_kicker_number(player_a_2)
            number_player_b_1 = get_current_kicker_number(player_b_1)
            number_player_b_2 = get_current_kicker_number(player_b_2)
        except NoKickerNumber:
            pass
        else:
            S = 1/2 + 180/7 * (goals_a - goals_b) / seconds
            E = 1 / (1 + 10**((number_player_a_1 + number_player_a_2 - number_player_b_1 - number_player_b_2) / 800))
            delta = S - E
            delta_a_1 = get_k(player_a_1) * delta
            delta_a_2 = get_k(player_a_2) * delta
            delta_b_1 = - get_k(player_b_1) * delta
            delta_b_2 = - get_k(player_b_2) * delta
            models.KickerNumber.objects.create(player=player_a_1, number=number_player_a_1 + delta_a_1, timestamp=now)
            models.KickerNumber.objects.create(player=player_a_2, number=number_player_a_2 + delta_a_2, timestamp=now)
            models.KickerNumber.objects.create(player=player_b_1, number=number_player_b_1 + delta_b_1, timestamp=now)
            models.KickerNumber.objects.create(player=player_b_2, number=number_player_b_2 + delta_b_2, timestamp=now)
        for shares in player_a_1.sold_shares.all():
            models.StockValue.objects.create(
                gambler=shares.owner, value=get_old_stock_value(shares.owner) + shares.number/100 * delta_a_1, timestamp=now)
        for shares in player_a_2.sold_shares.all():
            models.StockValue.objects.create(
                gambler=shares.owner, value=get_old_stock_value(shares.owner) + shares.number/100 * delta_a_2, timestamp=now)
        for shares in player_b_1.sold_shares.all():
            models.StockValue.objects.create(
                gambler=shares.owner, value=get_old_stock_value(shares.owner) + shares.number/100 * delta_b_1, timestamp=now)
        for shares in player_b_2.sold_shares.all():
            models.StockValue.objects.create(
                gambler=shares.owner, value=get_old_stock_value(shares.owner) + shares.number/100 * delta_b_2, timestamp=now)
        return respond_in_json(True)
