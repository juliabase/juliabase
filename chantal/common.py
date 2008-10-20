#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Common helper classes.  This is imported by various modules for having
common ground for pickling and unpickling of data structures, mostly for
statistical purposes."""

from __future__ import division
import re, datetime

remote_monitor_log_file_name = "/windows/T/public/bronger/remote_monitor.log"

class SystemInfo(object):
    def __init__(self, timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5):
        self.timestamp, self.used_mem, self.used_mem_with_buffers, self.used_swap, self.load_avg_5 = \
            timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5

class Availability(object):
    u"""Container for storing server availability data.

    FixMe: Describe attributes.
    """
    line_pattern = re.compile(ur"(?P<date>[-0-9 :]+)\s+(?P<type>[A-Z]+)\s+(?P<message>.*)")
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
