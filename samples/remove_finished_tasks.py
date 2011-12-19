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

"""This program removes the finished tasks from the database which are older
then a week.
It should be called once a day at night as a cron job.
Maybe run it after the postgresql_backup script to have a
backup, if needed.
"""

from samples.models import Task
import datetime

Task.objects.filter(status__contains="finished",
                    last_modified__lte=datetime.datetime.now() - datetime.timedelta(days=7)).delete()
