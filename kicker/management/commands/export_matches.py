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


"""Module which defines the command ``export_matches``.  It writes all Kicker
matches to ``/tmp/kicker_matches.json``.  This is a JSON file with a list of
entries of the following structure::

    {"timestamp": "2012-01-01T10:12:30.342Z",
     "team1": ["t.bronger", "m.nuys"],
     "team2": ["a.schmalen", "a.bauer"],
     "reporter": "t.bronger",
     "duration": 232,
     "score1": 4,
     "score2": 3
    }
"""

import json
from django.core.management.base import BaseCommand
from jb_common.utils.base import JSONEncoder
from kicker import models


class Command(BaseCommand):
    args = ""
    help = "Exports all Kicker matches to /tmp/kicker_matches.json."

    def handle(self, *args, **kwargs):
        matches = [{"timestamp": match.timestamp,
                    "team1": [match.player_a_1.username, match.player_a_2.username],
                    "team2": [match.player_b_1.username, match.player_b_2.username],
                    "score1": match.goals_a,
                    "score2": match.goals_b,
                    "duration": match.seconds,
                    "reporter": match.reporter.username} for match in models.Match.objects.filter(finished=True).iterator()]
        json.dump(matches, open("/tmp/kicker_matches.json", "w"), cls=JSONEncoder)
