#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

"""Importer fpr legacy kicker data.  It reads the same file format as Felo
(http://felo.sf.net)."""


from __future__ import absolute_import, division, unicode_literals

import datetime, re
from chantal_remote import *
from chantal_remote import connection
import cPickle as pickle

import ConfigParser, os
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

login(credentials["kicker_login"], credentials["kicker_password"], testserver=True)


old_timestamp_filename = "old_timestamp.pickle"
try:
    old_timestamp = pickle.load(open(old_timestamp_filename, "rb"))
except IOError:
    old_timestamp = datetime.datetime(2000, 1, 1)

inputfile = open("/home/chantal/kicker.felo")
while not inputfile.readline().startswith("="):
    pass

usernames = {
    "Aad": "a.gordijn",
    "Adrian": "__adrian",
    "Alain": "a.doumit",
    "Ali": "__ali",
    "Andre": "a.hoffmann",
    "Andrea": "a.muelheims",
    "Andreas": "and.bauer",
    "Arjan": "a.flikweert",
    "Beatrix": "b.blank",
    "Björn": "b.grootoonk",
    "Carsten": "c.grates",
    "Christian": "c.bock",
    "Christiane": "c.menke",
    "Christoph K": "__christoph_k",
    "Christian S": "c.sellmer",
    "Daniel": "d.weigand",
    "David": "d.wippler",
    "Eerke": "e.bunte",
    "Etienne": "e.moulin",
    "Florian": "f.koehler",
    "Gunnar": "g.schoepe",
    "Hang": "t.tran",
    "Harald": "__harald",
    "Jan": "j.woerdenweber",
    "Jan F": "j.flohre",
    "Jan H": "__jan_h",
    "Janine": "j.worbs",
    "Janis": "j.kroll",
    "Jose": "__jose",
    "Josef": "__josef_m",
    "Johannes": "j.wolff",
    "Jonas": "j.noll",
    "Jürgen": "j.huepkes",
    "Kah-Yoong": "__kah_yoong",
    "Kaining": "k.ding",
    "Katharina": "k.baumgartner",
    "Marek": "m.warzecha",
    "Markus H": "m.huelsbeck",
    "Markus": "m.ermes",
    "Matina": "__matina",
    "Maurice": "m.nuys",
    "Melanie": "me.schulte",
    "Michael": "__michael",
    "Peijing": "__peijing",
    "Philipp": "__philipp",
    "Pooria": "__pooria",
    "Rebecca": "r.van.aubel",
    "Robert": "__robert",
    "Roman": "__roman",
    "Sandra": "s.moll",
    "Sascha": "s.pust",
    "Silke": "s.lynen",
    "Sivei": "s.ku",
    "Stefan": "st.haas",
    "Stefan M": "s.muthmann",
    "Stephan": "s.lehnen",
    "Stephan K": "__stephan_kranz",
    "Steve": "__steve_r",
    "Susanne": "s.griesen",
    "Torsten": "t.bronger",
    "Toygan": "__toygan",
    "Tsveti": "t.merdzhanova",
    "Yuelong": "__yuelong",
    "Thomas Melle": "__thomas_melle",
    "Thomas B": "t.beckers",
    "Thomas K": "__thomas_kirchartz",
    "Thomas G": "__thomas_grundler",
    "Thomas": "t.zimmermann",
    "Timo": "__timo",
    "Thilo": "t.kilper",
    "Jan P": "__jan_p",
    "Joachim": "j.kirchhoff",
    "Michael B": "__michael_b",
    "Olivier": "o.thimm",
    "Dario": "__dario",
    "Ümit": "u.dagkaldiran",
    "Uli": "u.paetzold",
    "Uwe": "__uwe",
    "Dunja": "d.andriessen",
    "Jan B": "j.becker",
    "Jens": "j.bergmann",
    "Marvin": "m.goblet"}

start_numbers = {}
for line in inputfile:
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("="):
        break
    name, start_number = line.rsplit(None, 1)
    if name.startswith("("):
        name = name[1:-1]
    start_numbers[usernames[name]] = start_number


class LegacyMatch(object):
    timestamps = set()

    def __init__(self, player_a_1, player_a_2, player_b_1, player_b_2, goals_a, goals_b, timestamp):
        self.player_a_1, self.player_a_2, self.player_b_1, self.player_b_2, self.goals_a, self.goals_b, self.timestamp = \
            player_a_1, player_a_2, player_b_1, player_b_2, goals_a, goals_b, timestamp
        if goals_a + goals_b <= 7:
            self.seconds = 300
        else:
            self.seconds = 300/7 * (goals_a + goals_b)
        assert timestamp not in self.timestamps, timestamp
        self.timestamps.add(timestamp)

    def __lt__(self, other):
        return self.timestamp < other.timestamp

    def __str__(self):
        return "{0!r}  {1!r}  {2!r}  {3!r}  {4!r}  {5!r}  {6!r}  {7!r}".format(
            self.player_a_1, self.player_a_2, self.player_b_1, self.player_b_2, self.goals_a, self.goals_b, self.timestamp,
            self.seconds)


line_pattern = re.compile("(?P<date>[-0-9.]+)\s+(?P<player_a_1>[^/]+)/(?P<player_a_2>[^-]+) ?-- ?"
                          "(?P<player_b_1>[^/]+)/(?P<player_b_2>[^0-9]+)\s+(?P<goals_a>\d+):(?P<goals_b>\d+)",
                          re.UNICODE)
matches = []
start_timestamps = {}
current_date = None
for line in inputfile:
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    re_match = line_pattern.match(line)
    assert re_match
    date = re_match.group("date")
    if "." not in date:
        date = current_date + "." + date
    else:
        current_date = date[:10]
    new_timestamp = datetime.datetime.strptime(date, "%Y-%m-%d.%M")
    if new_timestamp > old_timestamp:
        player_a_1, player_a_2 = re_match.group("player_a_1"), re_match.group("player_a_2")
        player_b_1, player_b_2 = re_match.group("player_b_1"), re_match.group("player_b_2")
        player_a_1, player_a_2 = usernames[player_a_1.strip()], usernames[player_a_2.strip()]
        player_b_1, player_b_2 = usernames[player_b_1.strip()], usernames[player_b_2.strip()]
        start_timestamps.setdefault(player_a_1, new_timestamp)
        start_timestamps.setdefault(player_a_2, new_timestamp)
        start_timestamps.setdefault(player_b_1, new_timestamp)
        start_timestamps.setdefault(player_b_2, new_timestamp)
        if player_a_1 == player_a_2 and player_b_1 != player_b_2 or player_a_1 != player_a_2 and player_b_1 == player_b_2:
            print "3er-Match ignoriert"
            continue
        goals_a, goals_b = re_match.group("goals_a"), re_match.group("goals_b")
        goals_a, goals_b = int(goals_a), int(goals_b)
        matches.append(LegacyMatch(player_a_1, player_a_2, player_b_1, player_b_2, goals_a, goals_b, new_timestamp))


if old_timestamp == datetime.datetime(2000, 1, 1):
    for username, starting_number in start_numbers.iteritems():
        if username in start_timestamps:
            connection.open("kicker/starting_numbers/{0}/add/".format(username), {
                    "start_kicker_number": starting_number,
                    "timestamp": start_timestamps[username].strftime("%Y-%m-%d %H:%M:%S")})

for match in sorted(matches):
    connection.open("kicker/matches/add/", {
            "player_a_1": match.player_a_1,
            "player_a_2": match.player_a_2,
            "player_b_1": match.player_b_1,
            "player_b_2": match.player_b_2,
            "goals_a": match.goals_a,
            "goals_b": match.goals_b,
            "timestamp": match.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": match.seconds,
            "finished": True
            })

pickle.dump(new_timestamp, open(old_timestamp_filename, "wb"))
