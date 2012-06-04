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


"""Common helper classes.  This is imported by various modules for having
common ground for pickling and unpickling of data structures, mostly for
statistical purposes."""

from __future__ import division, unicode_literals
import re, datetime

remote_monitor_log_file_name = "/mnt/hobie/chantal_monitoring/remote_monitor.log"


class SystemInfo(object):
    def __init__(self, timestamp, used_mem_mandy, used_mem_olga, used_swap_mandy, used_swap_olga,
                 load_avg_5_mandy, load_avg_5_olga, db_hits):
        self.timestamp, self.used_mem_mandy, self.used_mem_olga, self.used_swap_mandy, self.used_swap_olga, \
            self.load_avg_5_mandy, self.load_avg_5_olga, self.db_hits = \
            timestamp, used_mem_mandy, used_mem_olga, used_swap_mandy, used_swap_olga, load_avg_5_mandy, load_avg_5_olga, \
            db_hits


class Availability(object):
    """Container for storing server availability data.

    FixMe: Describe attributes.
    """
    line_pattern = re.compile(r"(?P<date>[-0-9 :]+)\s+(?P<type>[A-Z]+)\s+(?P<message>.*)")

    def __init__(self, logfile_name=remote_monitor_log_file_name):
        self.downtime_intervals = []
        self.start_of_log = None
        up = down = 0
        start = None
        for line in open(logfile_name):
            linematch = self.line_pattern.match(line.strip())
            if linematch:
                date = datetime.datetime.strptime(linematch.group("date"), "%Y-%m-%d %H:%M:%S")
                if self.start_of_log is None:
                    self.start_of_log = date
                type_ = linematch.group("type")
                if type_ == "ERROR":
                    if start is None:
                        start = date
                    down += 1
                elif type_ == "INFO":
                    if start is not None:
                        self.downtime_intervals.append((start, date))
                        start = None
                    up += 1
        if start is not None:
            self.downtime_intervals.append((start, date))
        self.availability = up / (up + down) if up or down else None
