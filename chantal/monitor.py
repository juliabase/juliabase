#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
import subprocess, datetime, re, os, pickle, time

filename = "/home/bronger/repos/chantal/online/chantal/monitor.pickle"

def get_free_memory():
    free = subprocess.Popen(["free", "-b"], stdout=subprocess.PIPE)
    for line in free.stdout:
        match = total_pattern.match(line)
        if match:
            total = int(match.group(1))
        match = used_pattern.match(line)
        if match:
            used = int(match.group(1))
    return used/total*100

try:
    monitor_data = pickle.load(open(filename, "rb"))
except IOError:
    monitor_data = []

total_pattern = re.compile(r"Mem:\s*(\d+)")
used_pattern = re.compile(r"-/\+ buffers/cache:\s*(\d+)")
while True:
    now = datetime.datetime.now()
    new_data = (now, get_free_memory(), max(0, os.getloadavg()[1] - 1))
    monitor_data.append(new_data)
    while monitor_data and now - monitor_data[0][0] > datetime.timedelta(1.1):
        del monitor_data[0]
    pickle.dump(monitor_data, open(filename, "wb"))
    time.sleep(5*60)
