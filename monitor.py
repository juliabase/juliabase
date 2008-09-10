#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
import subprocess, datetime, re, os, pickle, time
from copy import copy

class SystemInfo(object):
    def __init__(self, timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5):
        self.timestamp, self.used_mem, self.used_mem_with_buffers, self.used_swap, self.load_avg_5 = \
            timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5

filename = "/home/bronger/repos/chantal/online/monitor.pickle"

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

while True:
    now = datetime.datetime.now()
    used, used_with_buffers, used_swap = get_free_memory()
    monitor_data.append(SystemInfo(now, used, used_with_buffers, used_swap, os.getloadavg()[1]))
    while monitor_data and now - monitor_data[0].timestamp > datetime.timedelta(1.1):
        del monitor_data[0]
    pickle.dump(monitor_data, open(filename, "wb"))
    time.sleep(5*60)
