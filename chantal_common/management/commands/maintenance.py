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


"""Module which defines the command ``maintenance``.  It should be called
nightly as a cronjob.  For example, one line in the crontab may read::

    0 3 * * * /home/chantal/chantal/manage.py maintenance
"""

from __future__ import absolute_import, unicode_literals

from django.core.management.base import BaseCommand
from chantal_common.signals import maintain


class Command(BaseCommand):
    args = ""
    help = "Does database maintenance work.  It should be called nightly as a cronjob."

    def handle(self, *args, **kwargs):
        maintain.send(sender=Command)
