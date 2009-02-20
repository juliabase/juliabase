#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""This program is supposed to run continuously on the server.  Normally, you
would start the process with::

    nohup ./monitor.py &

It is not necessary to be root for this.
"""

from __future__ import division
import subprocess, datetime, re, os, pickle, time
from chantal.common import SystemInfo, Availability
import psycopg2

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read("/var/lib/chantal/chantal.auth")
credentials = dict(credentials.items("DEFAULT"))


filename = "/home/www-data/online/monitor.pickle"
remote_monitor_pickle_file_name = "/home/www-data/online/remote_monitor.pickle"


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


def get_db_hits():
    connection = psycopg2.connect("user='chantal' password='%s'" % credentials["postgresql_password"]);
    cursor = connection.cursor()
    cursor.execute("SELECT tup_returned + tup_fetched + tup_inserted + tup_updated + tup_deleted "
                   "FROM pg_stat_database WHERE datname='chantal';")
    number_of_queries = cursor.fetchall()[0]
    connection.close()
    return number_of_queries


try:
    monitor_data = pickle.load(open(filename, "rb"))
except IOError:
    monitor_data = []


last_db_hits = None

while True:
    now = datetime.datetime.now()
    used, used_with_buffers, used_swap = get_free_memory()
    current_db_hits = get_db_hits()
    db_hits = 0 if last_db_hits is None else current - last_db_hits
    last_db_hits = current_db_hits
    monitor_data.append(SystemInfo(now, used, used_with_buffers, used_swap, os.getloadavg()[1], db_hits/(5*60)))
    while monitor_data and now - monitor_data[0].timestamp > datetime.timedelta(1.1):
        del monitor_data[0]
    pickle.dump(monitor_data, open(filename, "wb"))
    try:
        pickle.dump(Availability(), open(remote_monitor_pickle_file_name, "wb"))
    except IOError:
        pass
    time.sleep(5*60)
