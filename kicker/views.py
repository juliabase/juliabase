#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Kicker
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

from __future__ import division, absolute_import, unicode_literals

import datetime, os, math
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import matplotlib.dates
from django import forms
from django.forms.util import ValidationError
from django.conf import settings
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import django.contrib.auth.models
from django.http import Http404
from django.utils.translation import ugettext as _
from jb_common.utils import respond_in_json, JSONRequestException, get_really_full_name, successful_response, mkdirs, int_or_zero
from jb_common.signals import storage_changed
from samples.views import utils
from kicker import models


class NoKickerNumber(Exception):
    pass


def get_current_kicker_number(player):
    try:
        return models.KickerNumber.objects.filter(player=player).latest("timestamp").number
    except models.KickerNumber.DoesNotExist:
        raise NoKickerNumber


def average_goal_frequency(two_player_game):
    return 0.0310 if two_player_game else 0.0253


def average_match_duration(two_player_game):
    return 226 if two_player_game else 261


def get_elo_delta(goals_a, goals_b, number_player_a_1, number_player_a_2, number_player_b_1, number_player_b_2,
                  seconds, two_player_game):
    S = 1 / 2 + 1 / 2 * (goals_a - goals_b) / (seconds * average_goal_frequency(two_player_game))
    E = 1 / (1 + 10 ** ((number_player_b_1 + number_player_b_2 - number_player_a_1 - number_player_a_2) / 800))
    delta = math.sqrt(seconds / average_match_duration(two_player_game)) * (S - E)
    return delta


def get_current_kicker_number_or_estimate(player):
    try:
        return get_current_kicker_number(player)
    except NoKickerNumber:
        preliminary_kicker_number = 1500
        matches = list(models.Match.objects.filter(Q(player_a_1=player) | Q(player_a_2=player) | Q(player_b_1=player) |
                                                   Q(player_b_2=player)).filter(finished=True).distinct())
        # FixMe: This part is very inefficient.  One should collect the matches
        # *before* one enters the while loop.  This way, one avoids unnecessary
        # doubling of many operations.  On the other hand, one needs a new data
        # structure that holds the matches.  Fortunately, this is only rarely
        # needed.
        cycles_left = 50
        while cycles_left:
            cycles_left -= 1
            old_kicker_number = preliminary_kicker_number
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
                delta = get_elo_delta(match.goals_a, match.goals_b,
                                      number_player_a_1, number_player_a_2, number_player_b_1, number_player_b_2,
                                      match.seconds, two_player_game=match.player_a_1 == match.player_a_2)
                delta_player = 40 * delta
                if player in [match.player_b_1, match.player_b_2]:
                    delta_player = -delta_player
                preliminary_kicker_number += delta_player
                number_of_matches += 1
            if number_of_matches < 7:
                raise NoKickerNumber
            if abs(old_kicker_number - preliminary_kicker_number) < 1:
                break
        return preliminary_kicker_number


def get_k(player=None):
    return 24 if not player or models.KickerNumber.objects.filter(player=player).count() > 30 else 30


def get_old_stock_value(player):
    try:
        return models.StockValue.objects.filter(gambler=player).latest("timestamp")
    except models.StockValue.DoesNotExist:
        return 100


class MatchResult(object):

    def __init__(self, match):
        self.player_a_1, self.player_a_2, self.player_b_1, self.player_b_2 = \
            match.player_a_1, match.player_a_2, match.player_b_1, match.player_b_2
        self.timestamp = match.timestamp
        self.two_player_game = match.player_a_1 == match.player_a_2
        try:
            self.number_player_a_1 = get_current_kicker_number_or_estimate(self.player_a_1)
            self.number_player_a_2 = get_current_kicker_number_or_estimate(self.player_a_2)
            self.number_player_b_1 = get_current_kicker_number_or_estimate(self.player_b_1)
            self.number_player_b_2 = get_current_kicker_number_or_estimate(self.player_b_2)
        except NoKickerNumber:
            self.result_available = False
            self.expected_goal_difference = self.estimated_win_team_1 = None
        else:
            self.result_available = True
            delta = get_elo_delta(
                match.goals_a, match.goals_b,
                self.number_player_a_1, self.number_player_a_2, self.number_player_b_1, self.number_player_b_2,
                match.seconds, self.two_player_game)
            self.delta_a_1 = get_k(match.player_a_1) * delta
            self.delta_a_2 = get_k(match.player_a_2) * delta
            self.delta_b_1 = -get_k(match.player_b_1) * delta
            self.delta_b_2 = -get_k(match.player_b_2) * delta
            self.new_number_a_1 = self.number_player_a_1 + self.delta_a_1
            self.new_number_a_2 = self.number_player_a_2 + self.delta_a_2
            self.new_number_b_1 = self.number_player_b_1 + self.delta_b_1
            self.new_number_b_2 = self.number_player_b_2 + self.delta_b_2
            B = 10 ** ((self.number_player_b_1 + self.number_player_b_2 - self.number_player_a_1 - self.number_player_a_2)
                     / 800)
            self.expected_goal_difference = (1 / (1 + B) - 1 / 2) * \
                2 * average_goal_frequency(self.two_player_game) * average_match_duration(self.two_player_game)
            self.estimated_win_team_1 = get_k() * delta

    def add_kicker_numbers(self):
        if self.result_available:
            models.KickerNumber.objects.create(player=self.player_a_1, number=self.new_number_a_1, timestamp=self.timestamp)
            models.KickerNumber.objects.create(player=self.player_a_2, number=self.new_number_a_2, timestamp=self.timestamp)
            models.KickerNumber.objects.create(player=self.player_b_1, number=self.new_number_b_1, timestamp=self.timestamp)
            models.KickerNumber.objects.create(player=self.player_b_2, number=self.new_number_b_2, timestamp=self.timestamp)

    def add_stock_values(self):
        if self.result_available:
            for shares in self.player_a_1.sold_shares.all():
                models.StockValue.objects.create(
                    gambler=shares.owner,
                    value=get_old_stock_value(shares.owner) + shares.number / 100 * self.delta_a_1, timestamp=self.timestamp)
            for shares in self.player_a_2.sold_shares.all():
                models.StockValue.objects.create(
                    gambler=shares.owner,
                    value=get_old_stock_value(shares.owner) + shares.number / 100 * self.delta_a_2, timestamp=self.timestamp)
            for shares in self.player_b_1.sold_shares.all():
                models.StockValue.objects.create(
                    gambler=shares.owner,
                    value=get_old_stock_value(shares.owner) + shares.number / 100 * self.delta_b_1, timestamp=self.timestamp)
            for shares in self.player_b_2.sold_shares.all():
                models.StockValue.objects.create(
                    gambler=shares.owner,
                    value=get_old_stock_value(shares.owner) + shares.number / 100 * self.delta_b_2, timestamp=self.timestamp)


@login_required
@require_http_methods(["POST"])
def edit_match(request, id_=None):
    match = get_object_or_404(models.Match, pk=int_or_zero(id_)) if id_ else None
    if match and match.reporter != request.user:
        raise JSONRequestException(3005, "You must be the original reporter of this match.")
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
        timestamp = datetime.datetime.strptime(request.POST["timestamp"], "%Y-%m-%d %H:%M:%S")
    except KeyError as error:
        raise JSONRequestException(3, error.args[0])
    except ValueError as error:
        raise JSONRequestException(5, error.args[0])
    if not match:
        if player_a_1 == player_a_2 and player_b_1 != player_b_2 or player_a_1 != player_a_2 and player_b_1 == player_b_2:
            raise JSONRequestException(3000, "Games with three players can't be processed.")
        if player_a_1 == player_a_2 == player_b_1 == player_b_2:
            raise JSONRequestException(3001, "All players are the same person.")
        unfinished_matches = models.Match.objects.filter(finished=False)
        if unfinished_matches.exists():
            if unfinished_matches.exclude(reporter=request.user).exists():
                raise JSONRequestException(3004,
                                           "You can't add a match if another one of another reporter is not yet finished.")
            for match in unfinished_matches.all():
                match.delete()
    else:
        if match.finished:
            raise JSONRequestException(3003, "A finished match can't be edited anymore.")
        player_a_1 = match.player_a_1
        player_a_2 = match.player_a_2
        player_b_1 = match.player_b_1
        player_b_2 = match.player_b_2
    try:
        seconds_since_most_recent = (timestamp - models.Match.objects.latest("timestamp").timestamp).total_seconds()
        if seconds_since_most_recent <= 0:
            if seconds_since_most_recent < -10:
                raise JSONRequestException(3002, "This game is not the most recent one.")
            else:
                timestamp = models.Match.objects.latest("timestamp").timestamp + datetime.timedelta(seconds=1)
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
            goals_a=goals_a, goals_b=goals_b, timestamp=timestamp, finished=finished, seconds=seconds,
            reporter=request.user)
    if match.finished:
        if seconds <= 0:
            raise JSONRequestException(5, "Seconds must be positive.")
        match_result = MatchResult(match)
        match_result.add_kicker_numbers()
        match_result.add_stock_values()
    else:
        match.seconds = max(1, match.seconds)
        match_result = MatchResult(match)
    return respond_in_json((match.pk, match_result.expected_goal_difference, match_result.estimated_win_team_1))


@login_required
@require_http_methods(["POST"])
def cancel_match(request, id_):
    match = get_object_or_404(models.Match, pk=int_or_zero(id_)) if id_ else None
    if match and match.reporter != request.user:
        raise JSONRequestException(3005, "You must be the original reporter of this match.")
    if match.finished:
        raise JSONRequestException(3003, "A finished match can't be canceled.")
    match.delete()
    return respond_in_json(True)


@login_required
@require_http_methods(["POST"])
def set_start_kicker_number(request, username):
    if request.user.username != "kicker":
        raise JSONRequestException(3005, "You must be the user \"kicker\" to use this function.")
    try:
        start_kicker_number = int(request.POST["start_kicker_number"])
        timestamp = datetime.datetime.strptime(request.POST["timestamp"], "%Y-%m-%d %H:%M:%S")
    except KeyError:
        raise JSONRequestException(3, error.args[0])
    except ValueError as error:
        raise JSONRequestException(5, error.args[0])
    player, created = django.contrib.auth.models.User.objects.get_or_create(username=username)
    if created:
        player.set_unusable_password()
        player.save()
    if models.KickerNumber.objects.filter(player=player).exists():
        raise JSONRequestException(3006, "There are already kicker numbers stored for this user.")
    models.KickerNumber.objects.create(player=player, number=start_kicker_number, timestamp=timestamp)
    return respond_in_json(True)


def get_eligible_players():
    two_weeks_ago = datetime.datetime.now() - datetime.timedelta(weeks=2)
    ids = list(models.KickerNumber.objects.filter(timestamp__gt=two_weeks_ago).values_list("player", flat=True))
    eligible_players = list(django.contrib.auth.models.User.objects.in_bulk(ids).values())
    result = [(get_current_kicker_number_or_estimate(player), player) for player in eligible_players]
    result.sort(reverse=True)
    return [(entry[1], int(round(entry[0]))) for entry in result]


def plot_commands(axes, plot_data):
    for line in plot_data:
        if len(line[0]) == 1:
            line[0].append(line[0][0] - datetime.timedelta(days=1))
            line[1].append(line[1][0])
        axes.plot(line[0], line[1], label=line[2], linewidth=2)
    months_locator = matplotlib.dates.MonthLocator()
    axes.xaxis.set_major_locator(months_locator)
    months_formatter = matplotlib.dates.DateFormatter('%b')
    axes.xaxis.set_major_formatter(months_formatter)
    axes.grid(True)


def update_plot():
    path = os.path.join(settings.STATIC_ROOT, "kicker/")
#    if os.path.exists(os.path.join(path, "kicker.pdf")) and os.path.exists(os.path.join(path, "kicker.png")):
#        return
    eligible_players = [entry[0] for entry in get_eligible_players()]
    hundred_days_ago = datetime.datetime.now() - datetime.timedelta(days=100)
    plot_data = []
    for player in eligible_players:
        x_values, y_values = [], []
        latest_day = None
        kicker_numbers = list(models.KickerNumber.objects.filter(player=player, timestamp__gt=hundred_days_ago))
        for i, kicker_number in enumerate(kicker_numbers):
            if i == len(kicker_numbers) - 1 or \
                    kicker_numbers[i + 1].timestamp.toordinal() != kicker_number.timestamp.toordinal():
                x_values.append(kicker_number.timestamp)
                y_values.append(kicker_number.number)
        plot_data.append((x_values, y_values, player.kicker_user_details.nickname or player.username))
    figure = Figure(frameon=False, figsize=(8, 12))
    canvas = FigureCanvasAgg(figure)
    axes = figure.add_subplot(111)
    axes.set_position((0.1, 0.5, 0.8, 0.45))
    plot_commands(axes, plot_data)
    axes.legend(loc="upper center", bbox_to_anchor=[0.5, -0.1], ncol=3, shadow=True)
    mkdirs(path)
    canvas.print_figure(os.path.join(path, "kicker.png"))
    figure.clf()
    figure = Figure(frameon=False, figsize=(10, 7))
    canvas = FigureCanvasAgg(figure)
    axes = figure.add_subplot(111)
    axes.set_position((0.1, 0.1, 0.6, 0.8))
    plot_commands(axes, plot_data)
    axes.legend(loc="best", bbox_to_anchor=[1, 1], shadow=True)
    canvas.print_figure(os.path.join(path, "kicker.pdf"))
    figure.clf()
    storage_changed.send(models.KickerNumber)


@login_required
@require_http_methods(["GET"])
def summary(request):
    update_plot()
    eligible_players = get_eligible_players()
    return render(request, "kicker/summary.html", {"title": _("Kicker summary"), "kicker_numbers": eligible_players,
                                                   "latest_matches": models.Match.objects.reverse()[:20]})


class UserDetailsForm(forms.ModelForm):
    """Model form for user preferences.  I exhibit only two fields here, namely
    the nickname and the shortkey.
    """
    class Meta:
        model = models.UserDetails
        fields = ("nickname", "shortkey")

    def __init__(self, user, *args, **kwargs):
        super(UserDetailsForm, self).__init__(*args, **kwargs)
        self.user = user

    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"]
        if nickname and models.UserDetails.objects.exclude(user=self.user).filter(nickname=nickname).exists():
            raise ValidationError(_("This nickname is already given."))
        return nickname

    def clean_shortkey(self):
        shortkey = self.cleaned_data["shortkey"]
        if shortkey and models.UserDetails.objects.exclude(user=self.user).filter(shortkey=shortkey).exists():
            raise ValidationError(_("This shortkey is already given."))
        return shortkey


@login_required
def edit_user_details(request, username):
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if not request.user.is_staff and request.user != user:
        raise Http404("You can't access the user details of another user.")
    user_details = user.kicker_user_details
    if request.method == "POST":
        user_details_form = UserDetailsForm(user, request.POST, instance=user_details)
        if user_details_form.is_valid():
            user_details_form.save()
            return successful_response(request, _("The preferences were successfully updated."), summary)
    else:
        user_details_form = UserDetailsForm(user, instance=user_details)
    return render(request, "kicker/user_details.html", {
            "title": _("Change preferences for {user_name}").format(user_name=get_really_full_name(user)),
            "user_details": user_details_form})


@login_required
@require_http_methods(["GET"])
def get_player(request):
    try:
        user_details = models.UserDetails.objects.get(shortkey=request.GET.get("shortkey", ""))
    except (models.UserDetails.MultipleObjectsReturned, models.UserDetails.DoesNotExist):
        raise Http404("User not found.")
    return respond_in_json(
        (user_details.user.username, user_details.nickname or user_details.user.first_name or user_details.user.username))


start_number = 1300

def get_start_numbers():
    players = {}
    # FixMe: Exclude all matches for which is not 0 < S < 1 because they thwart
    # convergence.  They should be only a few.
    for i, match in enumerate(models.Match.objects.all()[:50]):
        players[match.player_a_1] = players[match.player_a_2] = \
            players[match.player_b_1] = players[match.player_b_2] = start_number
        if i / len(players) > 7:
            break
    if i / len(players) <= 7 and i < 49:
        return
    matches = list(models.Match.objects.all()[:i + 1])
    cycles_left = 1000
    while cycles_left:
        cycles_left -= 1
        old_players = players.copy()
        for match in matches:
            delta = get_elo_delta(match.goals_a, match.goals_b,
                                  players[match.player_a_1], players[match.player_a_2], players[match.player_b_1],
                                  players[match.player_b_2],
                                  match.seconds, two_player_game=match.player_a_1 == match.player_a_2)
            delta_player = 40 * delta
            players[match.player_a_1] += delta_player
            players[match.player_a_2] += delta_player
            players[match.player_b_1] -= delta_player
            players[match.player_b_2] -= delta_player
        if all(abs(players[player] - old_players[player]) < 1 for player in players):
            break
    else:
        return
    return players


def replay():
    models.KickerNumber.objects.all().delete()
    players = get_start_numbers()
    if not players:
        return
    zero_timestamp = models.Match.objects.all()[0].timestamp - datetime.timedelta(seconds=1)
    for player, start_number in players.items():
        models.KickerNumber.objects.create(player=player, number=start_number, timestamp=zero_timestamp)
    for match in models.Match.objects.iterator():
        MatchResult(match).add_kicker_numbers()
