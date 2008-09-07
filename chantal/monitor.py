#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
import subprocess, datetime, re, os, pickle, time

filename = "/home/bronger/repos/chantal/online/chantal/monitor.pickle"

total_pattern = re.compile(r"Mem:\s*(\d+)\s+(\d+)")
used_pattern = re.compile(r"-/\+ buffers/cache:\s*(\d+)")
def get_free_memory():
    free = subprocess.Popen(["free", "-b"], stdout=subprocess.PIPE)
    for line in free.stdout:
        match = total_pattern.match(line)
        if match:
            total, used_with_buffers = int(match.group(1)), int(match.group(2))
        match = used_pattern.match(line)
        if match:
            used = int(match.group(1))
    return used/total*100, used_with_buffers/total*100

try:
    monitor_data = pickle.load(open(filename, "rb"))
except IOError:
    monitor_data = []

while True:
    now = datetime.datetime.now()
    used, used_with_buffers = get_free_memory()
    new_data = (now, used, used_with_buffers, max(0, os.getloadavg()[1] - 1))
    monitor_data.append(new_data)
    while monitor_data and now - monitor_data[0][0] > datetime.timedelta(1.1):
        del monitor_data[0]
    pickle.dump(monitor_data, open(filename, "wb"))
    time.sleep(5*60)
