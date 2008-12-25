#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal_remote import *
import os, re, codecs, datetime

root_dir = "/home/bronger/temp/pds/"  # "/windows/T/daten/pds/"
database_path = "/home/bronger/temp/pdscpmdb/pds_tab.txt"  # "/windows/T/datenbank/pdscpmdb/PDS_tab.txt"

login("bronger", "*******")


def read_lines(filename):
    try:
        return codecs.open(filename, encoding="cp1252").readlines()
    except UnicodeDecodeError:
        try:
            return codecs.open(filename, encoding="cp437").readlines()
        except UnicodeDecodeError:
            return open(filename).readlines()


evaluated_data_files = {}
evaluated_filename_pattern = re.compile(r"a_pd(?P<number>\d+)(?P<suffix>.*)\.dat", re.IGNORECASE)
for directory, __, filenames in os.walk(root_dir):
    if os.path.basename(directory).startswith("p"):
        for filename in filenames:
            match = evaluated_filename_pattern.match(filename)
            if match:
                number = int(match.group("number"))
                evaluated_data_files[number] = os.path.join(directory, filename)


date_pattern = re.compile(r"#?(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2,4})")
date2_pattern = re.compile(r"(?P<day>\d{1,2})\s*(?P<month>[A-Za-z]{3})\s+(?P<year>\d{4})")
def parse_date(datestring):
    match = date_pattern.match(datestring)
    if match:
        year = int(match.group("year"))
        if year < 100:
            year = 1900 + year if year > 40 else 2000 + year
        return datetime.datetime(year, int(match.group("month")), int(match.group("day")), 10, 0)
    match = date2_pattern.match(datestring)
    if match:
        month = [None, "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].\
            index(match.group("month"))
        return datetime.datetime(int(match.group("year")), month, int(match.group("day")), 10, 0)


def extract_comments(filename):
    comment_lines = []
    for linenumber, line in enumerate(read_lines(filename)):
        linenumber += 1
        line = line.strip()
        if line.startswith("BEGIN") or linenumber >= 21:
            break
        if linenumber >= 5:
            comment_lines.append(line)
    comments = u"\n".join(comment_lines) + "\n"
    while "\n\n" in comments:
        comments = comments.replace("\n\n", "\n")
    if comments.startswith("\n"):
        comments = comments[1:]
    return comments


raw_filename_pattern = re.compile(r"pd(?P<number>\d+)\.dat", re.IGNORECASE)

class LegacyPDSMeasurement(object):

    def __init__(self, line):
        self.path, filename, self.date, self.sample_name, self.substrate, self.material, self.remarks = \
            line.strip().split(";", 6)
        match = raw_filename_pattern.match(filename)
        if match:
            self.number = int(match.group("number"))
        else:
            raise ValueError
        self.date = parse_date(self.date)
        dirname = os.path.join(root_dir, os.path.basename(self.path[:-1].replace("\\", "/")))
        self.path = os.path.join(dirname, filename)
        if not os.path.exists(self.path):
            raise ValueError
        self.comments = extract_comments(self.path)
        if not self.comments.startswith(self.remarks):
            self.comments = u"Abweichende Angaben in Datenbank und Messdatei!\n"
        self.evaluated_path = evaluated_data_files.get(self.number)


pds_measurements = []
for line in open(database_path):
    try:
        pds_measurements.append(LegacyPDSMeasurement(line))
    except ValueError:
        pass

for legacy_pds_measurement in pds_measurements:
    if len(legacy_pds_measurement.sample_name) > 2 and legacy_pds_measurement.sample_name[2].upper() not in ["L", "B"]:
        continue
    sample_id = get_or_create_sample(legacy_pds_measurement.sample_name)
    if sample_id is not None:
        pds_measurement = PDSMeasurement(sample_id)
        pds_measurement.number = legacy_pds_measurement.number
        pds_measurement.timestamp = legacy_pds_measurement.date
        pds_measurement.timestamp_inaccuracy = 3
        pds_measurement.raw_datafile = legacy_pds_measurement.path[len(root_dir):]
        if legacy_pds_measurement.evaluated_path:
            pds_measurement.evaluated_datafile = legacy_pds_measurement.evaluated_path[len(root_dir):]
        pds_measurement.comments = legacy_pds_measurement.comments
        pds_measurement.submit()

logout()
