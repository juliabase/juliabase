#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""This program is supposed to run continuously on the server.  Normally, you
would start the process with::

    nohup ./monitor.py &

It is not necessary to be root for this, however, it may be necessary to adjust
`filename`.
"""

from __future__ import division
import subprocess, datetime, re, os, pickle, time
from copy import copy

class SystemInfo(object):
    def __init__(self, timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5):
        self.timestamp, self.used_mem, self.used_mem_with_buffers, self.used_swap, self.load_avg_5 = \
            timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5

filename = "/home/bronger/repos/chantal/online/monitor.pickle"
remote_monitor_log_file_name = "/windows/hobie/remote_monitor.log"
remote_monitor_pickle_file_name = "/home/bronger/repos/chantal/online/remote_monitor.pickle"

total_pattern = re.compile(r"Mem:\s*(\d+)\s+(\d+)")
used_pattern = re.compile(r"-/\+ buffers/cache:\s*(\d+)")
swap_pattern = re.compile(r"Swap:\s*(\d+)\s+(\d+)")
def get_free_memory():
    free = subprocess.Popen(["free", "-b"], stdout=subprocess.PIPE)
    for line in free.stdout:
        match = total_pattern.match(line)
        if match:
            total, used_with_buffers = int(match.group(1)), int(match.group(2))
        match = used_pattern.match(line)
        if match:
            used = int(match.group(1))
        match = swap_pattern.match(line)
        if match:
            swap, swap_used = int(match.group(1)), int(match.group(2))
    return used/total*100, used_with_buffers/total*100, swap_used/swap*100

try:
    monitor_data = pickle.load(open(filename, "rb"))
except IOError:
    monitor_data = []

if isinstance(monitor_data[0], tuple):
    old_monitor_data = copy(monitor_data)
    monitor_data = []
    for data in old_monitor_data:
        monitor_data.append(SystemInfo(data[0], data[1], data[2], 0, data[3]+1))

class Availability(object):
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

while True:
    now = datetime.datetime.now()
    used, used_with_buffers, used_swap = get_free_memory()
    monitor_data.append(SystemInfo(now, used, used_with_buffers, used_swap, os.getloadavg()[1]))
    while monitor_data and now - monitor_data[0].timestamp > datetime.timedelta(1.1):
        del monitor_data[0]
    pickle.dump(monitor_data, open(filename, "wb"))
    pickle.dump(Availability(), open(remote_monitor_pickle_file_name, "wb"))
    time.sleep(5*60)
