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


"""This program should run every 10 minutes as a cronjob.  It should not run
with root priviledges.  Its purpose is to generate a new plot file which is
written to the file with the name `filename`.  It reads the logs of Apache and
PostgreSQL server and the monitor data from `monitor_file_name`.
"""

from __future__ import division, unicode_literals

import sys, os.path
sys.path.append(os.path.expanduser("/home/chantal/chantal"))

import glob, gzip, re, datetime, math, pickle, socket, subprocess
import matplotlib, numpy
matplotlib.use("Agg")
import pylab


filename = "/var/www/chantal/media/server_load.png"
monitor_file_name = "/mnt/hobie/chantal_monitoring/monitor.pickle"
binning = 60
"""Number of seconds that are combined to the sample x value in the plot
data"""

number_of_slots = 24 * 3600 // binning

now = datetime.datetime.now()

local_hostname = socket.gethostname()


def timedelta_to_seconds(timedelta):
    return timedelta.days * 3600 * 24 + timedelta.seconds + timedelta.microseconds * 1e-6


apache_date_pattern = re.compile(r".*\[(?P<date>[:/0-9a-zA-Z]+) [+0-9]+\]")

def read_times_apache(hostname):
    logdir = "/tmp/apache_logs"
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    if hostname == local_hostname:
        log_glob = "/var/log/apache2/other_vhosts_access.log*"
    else:
        host_ip = {"mandy": "192.168.26.130", "olga": "192.168.26.131"}[hostname]
        subprocess.check_call(["rsync", "-avuz", "{0}:/var/log/apache2/other_vhosts_access.log*".format(host_ip), logdir])
        log_glob = os.path.join(logdir, "other_vhosts_access.log*")
    times = number_of_slots * [0]
    read_further = True
    for filename in sorted(glob.glob(log_glob)):
        if filename.endswith(".gz"):
            logfile = gzip.open(filename)
        else:
            logfile = open(filename)
        for linenumber, line in enumerate(logfile):
            date = apache_date_pattern.match(line).group("date")
            timestamp = datetime.datetime.strptime(date, "%d/%b/%Y:%H:%M:%S")
            timedelta = now - timestamp
            timedelta_seconds = int(round(timedelta_to_seconds(timedelta)))
            index = (24 * 3600 - timedelta_seconds) // binning
            if 0 <= index < number_of_slots:
                times[index] += 1 / binning
            elif linenumber == 0:
                read_further = False
        logfile.close()
        if not read_further:
            break
    return times


window_half_width = 10 * 60 // binning

def mollifier(x):
    if -window_half_width < x < window_half_width:
        return 2.252283621 / window_half_width * math.exp(-1 / (1 - (x / window_half_width) ** 2))
    else:
        return 0


def mollify(times):
    rps = []
    for i in range(window_half_width, number_of_slots - window_half_width):
        integral = 0
        for j in range(i - window_half_width, i + window_half_width + 1):
            integral += times[j] * mollifier(i - j)
        rps.append(integral)
    return window_half_width * [rps[0]] + rps + window_half_width * [rps[-1]]


def read_monitor_data():
    def interpolate(attribute):
        return (timedelta_to_seconds(timestamp - monitor_data[j - 1].timestamp) /
                timedelta_to_seconds(monitor_data[j].timestamp - monitor_data[j - 1].timestamp) *
                (getattr(monitor_data[j], attribute) - getattr(monitor_data[j - 1], attribute)) +
                getattr(monitor_data[j - 1], attribute))
    monitor_data = pickle.load(open(monitor_file_name, "rb"))
    for i, data in enumerate(monitor_data):
        monitor_data[i].db_hps = monitor_data[i].db_hits - monitor_data[i - 1].db_hits if i > 0 else 0  # hits per second
        if monitor_data[i].db_hps < 0:
            # This can happen when Postgres was restarted
            monitor_data[i].db_hps = monitor_data[i - 1].db_hps
    memory_usage_mandy = []
    memory_usage_olga = []
    swap_usage_mandy = []
    swap_usage_olga = []
    load_avgs_mandy = []
    load_avgs_olga = []
    db_hps = []
    for i in range(number_of_slots):
        timestamp = now + datetime.timedelta(-1 + i / number_of_slots)
        j = 0
        while j < len(monitor_data) and monitor_data[j].timestamp < timestamp:
            j += 1
        if j == len(monitor_data):
            memory_usage_mandy.append(monitor_data[-1].used_mem_mandy)
            memory_usage_olga.append(monitor_data[-1].used_mem_olga)
            swap_usage_mandy.append(monitor_data[-1].used_swap_mandy)
            swap_usage_olga.append(monitor_data[-1].used_swap_olga)
            load_avgs_mandy.append(monitor_data[-1].load_avg_5_mandy)
            load_avgs_olga.append(monitor_data[-1].load_avg_5_olga)
            db_hps.append(monitor_data[-1].db_hps)
        elif j == 0:
            memory_usage_mandy.append(0)
            memory_usage_olga.append(0)
            swap_usage_mandy.append(0)
            swap_usage_olga.append(0)
            load_avgs_mandy.append(0)
            load_avgs_olga.append(0)
            db_hps.append(0)
        else:
            memory_usage_mandy.append(interpolate("used_mem_mandy"))
            memory_usage_olga.append(interpolate("used_mem_olga"))
            swap_usage_mandy.append(interpolate("used_swap_mandy"))
            swap_usage_olga.append(interpolate("used_swap_olga"))
            load_avgs_mandy.append(interpolate("load_avg_5_mandy"))
            load_avgs_olga.append(interpolate("load_avg_5_olga"))
            db_hps.append(interpolate("db_hps"))
    return memory_usage_mandy, memory_usage_olga, swap_usage_mandy, swap_usage_olga, load_avgs_mandy, load_avgs_olga, db_hps


def expand_array(array, with_nulls=True):
    if with_nulls:
        return [0] + array + [0]
    else:
        return array[:1] + array + array[-1:]


pylab.figure(figsize=(8, 9))
pylab.subplots_adjust(bottom=0.05, right=0.95, top=0.95, hspace=0.3)
x_values = expand_array(list(numpy.arange(0, 24, 24 / number_of_slots)), with_nulls=False)
locations = list(numpy.arange(1 - now.minute / 60 + (now.hour + 1) % 2, 25, 2))
if locations[-1] > 24:
    del locations[-1]
labels = len(locations) * [""]

rps_apache_mandy = expand_array(mollify(read_times_apache("mandy")))
rps_apache_olga = expand_array(mollify(read_times_apache("olga")))
pylab.subplot(411)
pylab.fill(x_values, rps_apache_mandy, edgecolor="none", facecolor="#d0a2a2", closed=False)
pylab.fill(x_values, rps_apache_olga, edgecolor="none", facecolor="#d0a2a2", closed=False)
pylab.plot(x_values, rps_apache_mandy, color="#800000", linewidth=1.5)
pylab.plot(x_values, rps_apache_olga, color="#800000")
pylab.title("Apache server load")
pylab.xlim(0, 24)
pylab.ylabel("requests/sec")
pylab.xticks(locations, labels)

memory_usage_mandy, memory_usage_olga, swap_usage_mandy, swap_usage_olga, load_avgs_mandy, load_avgs_olga, db_hps = \
    read_monitor_data()
memory_usage_mandy, memory_usage_olga, swap_usage_mandy, swap_usage_olga, load_avgs_mandy, load_avgs_olga, db_hps = \
    expand_array(mollify(memory_usage_mandy)), expand_array(mollify(memory_usage_olga)), \
    expand_array(mollify(swap_usage_mandy), with_nulls=False), expand_array(mollify(swap_usage_olga), with_nulls=False), \
    expand_array(mollify(load_avgs_mandy)), expand_array(mollify(load_avgs_olga)), expand_array(mollify(db_hps))

pylab.subplot(412)
pylab.fill(x_values, db_hps, edgecolor="b", facecolor="#bbbbff", closed=False)
pylab.title("PostgreSQL server load")
pylab.xticks(locations, labels)
pylab.xlim(0, 24)
pylab.ylabel("rows/sec")

pylab.subplot(413)
pylab.fill(x_values, load_avgs_mandy, edgecolor="none", facecolor="#c2c2c2", closed=False)
pylab.fill(x_values, load_avgs_olga, edgecolor="none", facecolor="#c2c2c2", closed=False)
pylab.plot(x_values, load_avgs_mandy, color="k", linewidth=1.5)
pylab.plot(x_values, load_avgs_olga, color="k")
pylab.title("CPU load")
pylab.xticks(locations, labels)
pylab.xlim(0, 24)
pylab.ylabel("load average 5")

pylab.subplot(414)
pylab.fill(x_values, memory_usage_mandy, edgecolor="none", facecolor="#bbffbb", closed=False)
pylab.fill(x_values, memory_usage_olga, edgecolor="none", facecolor="#bbffbb", closed=False)
pylab.plot(x_values, memory_usage_mandy, color="g", linewidth=1.5)
pylab.plot(x_values, memory_usage_olga, color="g")
pylab.plot(x_values, swap_usage_mandy, "r", linewidth=1.5)
pylab.plot(x_values, swap_usage_olga, "r")
pylab.title("Memory usage")
pylab.xticks(numpy.arange(1 - now.minute / 60 + (now.hour + 1) % 2, 25, 2),
             [str(i % 24) for i in range((now.hour - 23 + (now.hour + 1) % 2) % 24, 100, 2)])
pylab.xlim(0, 24)
pylab.ylabel("usage %")
pylab.xlabel("time")

pylab.savefig(open(filename, "wb"), facecolor=("#e6e6e6"), edgecolor=("#e6e6e6"))


remote_hostname = "192.168.26.131" if local_hostname == "mandy" else "192.168.26.130"
subprocess.check_call(["rsync", "-avuz", "/var/www/chantal/media/", "{0}:/var/www/chantal/media/".format(remote_hostname)])
