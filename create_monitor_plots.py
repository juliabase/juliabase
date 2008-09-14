#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""This program should run every 10 minutes as a cronjob.  It should not run
with root priviledges.  Its purpose is to generate a new plot file which is
written to the file with the name `filename`.  It reads the logs of Apache and
MySQL server and the monitor data from `monitor_file_name`.
"""

from __future__ import division
import glob, gzip, re, datetime, math, pickle, os
import matplotlib, matplotlib.numerix
matplotlib.use("Agg")
import pylab

class SystemInfo(object):
    def __init__(self, timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5):
        self.timestamp, self.used_mem, self.used_mem_with_buffers, self.used_swap, self.load_avg_5 = \
            timestamp, used_mem, used_mem_with_buffers, used_swap, load_avg_5

filename = "/home/bronger/repos/chantal/online/chantal/media/server_load.png"
monitor_file_name = "/home/bronger/repos/chantal/online/monitor.pickle"
binning = 60
u"""Number of seconds that are combined to the sample x value in the plot
data"""

number_of_slots = 24*3600//binning

now = datetime.datetime.now()

def timedelta_to_seconds(timedelta):
    return timedelta.days*3600*24 + timedelta.seconds + timedelta.microseconds*1e-6

apache_date_pattern = re.compile(ur".*\[(?P<date>[:/0-9a-zA-Z]+) [+0-9]+\]")
def read_times_apache():
    times = number_of_slots * [0]
    read_further = True
    for filename in sorted(glob.glob("/var/log/apache2/access.log*")):
        if filename.endswith(".gz"):
            logfile = gzip.open(filename)
        else:
            logfile = open(filename)
        for linenumber, line in enumerate(logfile):
            date = apache_date_pattern.match(line).group("date")
            timestamp = datetime.datetime.strptime(date, "%d/%b/%Y:%H:%M:%S")
            timedelta = now - timestamp
            timedelta_seconds = int(round(timedelta_to_seconds(timedelta)))
            index = (24*3600 - timedelta_seconds)//binning
            if 0 <= index < number_of_slots:
                times[index] += 1/binning
            elif linenumber == 0:
                read_further = False
        logfile.close()
        if not read_further:
            break
    return times

mysql_date_pattern = re.compile(ur"^\d{6} (\d| )\d:\d\d:\d\d")
db_hit_pattern = re.compile(ur"(\d{6} (\d| )\d:\d\d:\d\d)?\s+\d+ Query\s+(SELECT|DELETE|INSERT|ALTER|CREATE|UPDATE|SHOW)")
def read_times_mysql():
    times = number_of_slots * [0]
    read_further = True
    for filename in sorted(glob.glob("/var/log/mysql/mysql.log*")):
        if filename.endswith(".gz"):
            logfile = gzip.open(filename)
        else:
            logfile = open(filename)
        timedelta = datetime.timedelta(0)
        index = -1
        for linenumber, line in enumerate(logfile):
            date_match = mysql_date_pattern.match(line)
            if date_match:
                date = date_match.group()
                if date[7] == " ":
                    date = date[:7] + "0" + date[8:]
                timestamp = datetime.datetime.strptime(date, "%y%m%d %H:%M:%S")
                timedelta = now - timestamp
                timedelta_seconds = int(round(timedelta_to_seconds(timedelta)))
                index = (24*3600 - timedelta_seconds)//binning
            if 0 <= index < number_of_slots and db_hit_pattern.match(line):
                times[(24*3600 - timedelta.seconds)//binning] += 1/binning
            elif linenumber == 0:
                read_further = False
        logfile.close()
        if not read_further:
            break
    return times

window_half_width = 5*60//binning
def mollifier(x):
    if -window_half_width < x < window_half_width:
        return 2.252283621/window_half_width * math.exp(-1/(1-(x/window_half_width)**2))
    else:
        return 0

def mollify(times):
    rps = []
    for i in range(window_half_width, number_of_slots-window_half_width):
        integral = 0
        for j in range(i-window_half_width, i+window_half_width+1):
            integral += times[j] * mollifier(i - j)
        rps.append(integral)
    return window_half_width*[rps[0]] + rps + window_half_width*[rps[-1]]

def read_monitor_data():
    def interpolate(attribute):
        return (timedelta_to_seconds(timestamp - monitor_data[j-1].timestamp) /
                timedelta_to_seconds(monitor_data[j].timestamp - monitor_data[j-1].timestamp) *
                (getattr(monitor_data[j], attribute) - getattr(monitor_data[j-1], attribute)) +
                getattr(monitor_data[j-1], attribute))
    monitor_data = pickle.load(open(monitor_file_name, "rb"))
    for data in monitor_data:
        data.load_avg_5 = max(0, data.load_avg_5 - 1)
    memory_usage = []
    memory_with_buffers_usage = []
    swap_usage = []
    load_avgs = []
    for i in range(number_of_slots):
        timestamp = now + datetime.timedelta(-1 + i/number_of_slots)
        j = 0
        while j < len(monitor_data) and monitor_data[j].timestamp < timestamp:
            j += 1
        if j == len(monitor_data):
            memory_usage.append(monitor_data[-1].used_mem)
            memory_with_buffers_usage.append(monitor_data[-1].used_mem_with_buffers)
            swap_usage.append(monitor_data[-1].used_swap)
            load_avgs.append(monitor_data[-1].load_avg_5)
        elif j == 0:
            memory_usage.append(0)
            memory_with_buffers_usage.append(0)
            swap_usage.append(0)
            load_avgs.append(0)
        else:
            memory_usage.append(interpolate("used_mem"))
            memory_with_buffers_usage.append(interpolate("used_mem_with_buffers"))
            swap_usage.append(interpolate("used_swap"))
            load_avgs.append(interpolate("load_avg_5"))
    return memory_usage, memory_with_buffers_usage, swap_usage, load_avgs

def expand_array(array, with_nulls=True):
    if with_nulls:
        return [0] + array + [0]
    else:
        return array[:1] + array + array[-1:]

pylab.figure(figsize=(8, 9))
pylab.subplots_adjust(bottom=0.05, right=0.95, top=0.95, hspace=0.3)
x_values = expand_array(list(matplotlib.numerix.arange(0, 24, 24/number_of_slots)), with_nulls=False)
locations = list(matplotlib.numerix.arange(1-now.minute/60 + (now.hour+1)%2, 25, 2))
if locations[-1] > 24:
    del locations[-1]
labels = len(locations) * [u""]

rps_apache = expand_array(mollify(read_times_apache()))
pylab.subplot(411)
pylab.fill(x_values, rps_apache, edgecolor="#800000", facecolor="#d0a2a2", closed=False)
pylab.title(u"Apache server load")
pylab.xlim(0, 24)
pylab.ylabel(u"requests/sec")
pylab.xticks(locations, labels)

pylab.subplot(412)
rps_mysql = expand_array(mollify(read_times_mysql()))
pylab.fill(x_values, rps_mysql, edgecolor="b", facecolor="#bbbbff", closed=False)
pylab.title(u"MySQL server load")
pylab.xticks(locations, labels)
pylab.xlim(0, 24)
pylab.ylabel(u"queries/sec")

memory_usage, memory_with_buffers_usage, swap_usage, load_avgs = read_monitor_data()
memory_usage, memory_with_buffers_usage, swap_usage, load_avgs = \
    expand_array(mollify(memory_usage)), expand_array(mollify(memory_with_buffers_usage)), \
    expand_array(mollify(swap_usage), with_nulls=False), expand_array(mollify(load_avgs))

pylab.subplot(413)
pylab.fill(x_values, load_avgs, edgecolor="k", facecolor="#c2c2c2", closed=False)
pylab.title(u"CPU load")
pylab.xticks(locations, labels)
pylab.xlim(0, 24)
pylab.ylabel(u"load average 5")

pylab.subplot(414)
pylab.fill(x_values, memory_with_buffers_usage, x_values, memory_usage, edgecolor="g", facecolor="#bbffbb", closed=False)
pylab.plot(x_values, swap_usage, "r")
pylab.title(u"Memory usage")
pylab.xticks(matplotlib.numerix.arange(1-now.minute/60 + (now.hour+1)%2, 25, 2),
             [str(i%24) for i in range((now.hour-23+(now.hour+1)%2)%24, 100, 2)])
pylab.xlim(0, 24)
pylab.ylabel(u"usage %")
pylab.xlabel(u"time")

pylab.savefig(open(filename, "wb"), facecolor=("#e6e6e6"), edgecolor=("#e6e6e6"))
