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


"""This program is supposed to run as a cronjob of the user "chantal" every 5
minutes.  It must run only on one node.
"""

from __future__ import division, unicode_literals

import sys, os.path
sys.path.append(os.path.expanduser("~/chantal"))

import subprocess, datetime, re, pickle, socket
from tools.common import SystemInfo, Availability
import psycopg2

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read("/var/www/chantal.auth")
credentials = dict(credentials.items("DEFAULT"))


filename = "/mnt/hobie/chantal_monitoring/monitor.pickle"
remote_monitor_pickle_file_name = "/mnt/hobie/chantal_monitoring/remote_monitor.pickle"


local_hostname = socket.gethostname()


total_pattern = re.compile(r"Mem:\s*(\d+)\s+(\d+)")
used_pattern = re.compile(r"-/\+ buffers/cache:\s*(\d+)")
swap_pattern = re.compile(r"Swap:\s*(\d+)\s+(\d+)")

def get_free_memory(hostname):
    if hostname == local_hostname:
        free = subprocess.Popen(["free", "-b"], stdout=subprocess.PIPE)
    else:
        free = subprocess.Popen(["ssh", hostname, "free -b"], stdout=subprocess.PIPE)
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

def get_load_average_5(hostname):
    if hostname == local_hostname:
        load = subprocess.Popen(["cat", "/proc/loadavg"], stdout=subprocess.PIPE)
    else:
        load = subprocess.Popen(["ssh", hostname, "cat /proc/loadavg"], stdout=subprocess.PIPE)
    loadavg5 = float(load.communicate()[0].split()[1])
    return loadavg5


def get_db_hits():
    connection = psycopg2.connect("user='{postgresql_user}' password='{postgresql_password}' "
                                  "host='192.168.26.132'".format(**credentials))
    cursor = connection.cursor()
    cursor.execute("SELECT tup_fetched / 100.0 + tup_inserted + tup_deleted FROM pg_stat_database WHERE datname='chantal';")
    number_of_queries = int(round(cursor.fetchall()[0][0]))
    connection.close()
    return number_of_queries


try:
    monitor_data = pickle.load(open(filename, "rb"))
except IOError:
    monitor_data = []


now = datetime.datetime.now()
used_mandy, __, used_swap_mandy = get_free_memory("mandy")
used_olga, __, used_swap_olga = get_free_memory("olga")
monitor_data.append(SystemInfo(now, used_mandy, used_olga, used_swap_mandy, used_swap_olga,
                               get_load_average_5("mandy"), get_load_average_5("olga"), get_db_hits() / 300))
while monitor_data and now - monitor_data[0].timestamp > datetime.timedelta(1.1):
    del monitor_data[0]
pickle.dump(monitor_data, open(filename, "wb"))
pickle.dump(Availability(), open(remote_monitor_pickle_file_name, "wb"))
