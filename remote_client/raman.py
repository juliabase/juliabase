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


from __future__ import unicode_literals
from chantal_remote import *
import os, os.path, re, codecs, datetime, logging, glob
import csv, cStringIO

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

root_dir = "/windows/T/daten/"

login(credentials["crawlers_login"], credentials["crawlers_password"])


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)
    def __iter__(self):
        return self
    def next(self):
        return self.reader.next().encode("utf-8")

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """
    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwargs):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwargs)
    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]
    def __iter__(self):
        return self

class SinglePathFound(Exception):
    def __init__(self, path):
        self.path = path

class NoSinglePathFound(Exception):
    def __init__(self, paths):
        self.paths = paths

def guess_single_filename(filepaths, measurement):
    def filter_paths(condition):
        new_filepaths = [path for path in filepaths if condition(path)]
        if len(new_filepaths) == 1:
            raise SinglePathFound(new_filepaths[0])
        elif not new_filepaths:
            return filepaths
        else:
            return new_filepaths
    filepaths = [filepath for filepath in filepaths if not filepath.endswith("raman/s.klein/488/05C047C2.PRN")]
    try:
        filepaths = filter_paths(lambda path: True)
        filepaths = filter_paths(lambda path: measurement["excitation_wavelength"] in path)
        filepaths = filter_paths(lambda path: measurement["manufacturer"].replace("ö", "oe").replace("ä", "ae").
                                 replace("ü", "ue").replace("ß", "ss") in path)
    except SinglePathFound as e:
        return e.path
    raise NoSinglePathFound(filepaths)

filepaths = set()
filename_pattern = re.compile(r".+\.(prn|asc)", re.IGNORECASE)
files = {}
for sub_path in ["raman", "raman_2"]:
    root_path = os.path.join(root_dir, sub_path)
    for dirname, __, filenames in os.walk(root_path):
        for filename in filenames:
            if filename_pattern.match(filename):
                filepath = os.path.join(dirname, filename)
                filepaths.add(filepath)
                files.setdefault(os.path.splitext(filename)[0].lower(), []).append(filepath)

acme_quirky_sample_name_pattern = re.compile(r"TS\d{4}/\d$", re.IGNORECASE)
acme_sample_pattern = re.compile(r"(?P<initials>JH|SW|JG|JL|SL|TS|mm|ST|MI|SK)(?P<number>\d{4})-(?P<index>\d+)",
                                 re.IGNORECASE)
def normalize_acme_name(sample_name):
    sample_name = sample_name.upper()
    if sample_name.startswith("MM"):
        sample_name = sample_name.lower()
    return sample_name
acme_raw_files = {}
acme_evaluated_files = {}
for filename in glob.glob(os.path.join(root_dir, "0_projekte/ACME01/Raman/rohdaten", "*")):
    if filename_pattern.match(filename):
        match = acme_sample_pattern.match(os.path.basename(filename))
        if match:
            sample_name = normalize_acme_name(match.group(0))
            acme_raw_files[sample_name] = filename[len(root_dir):]
            evaluated_filepath = os.path.join(root_dir, "0_projekte/ACME01/Raman/korrigiertedaten",
                                              os.path.splitext(os.path.basename(filename))[0] + "_kalk.rat")
            if os.path.exists(evaluated_filepath):
                acme_evaluated_files[sample_name] = evaluated_filepath[len(root_dir):]

through_substrate_pattern = re.compile(r"Rüp?ckseite|Glasseite", re.IGNORECASE | re.UNICODE)
measurements_on_day = {}
consumed_filepaths = set()
measurements = []
for number, columns in [(1, ["number", "date", "manufacturer", "sample", "datafile", "substrate", "central_wavelength",
                             "excitation_wavelength", "slit", "accumulation", "time", "laser_power", "icrs", "comments"]),
                        (2, ["number", "date", "manufacturer", "sample", "datafile", "substrate", "central_wavelength",
                             "excitation_wavelength", "slit", "accumulation", "time", "laser_power", "grating", "objective",
                             "icrs", "comments"])]:
    reader = UnicodeReader(open("raman_{0}.csv".format(number), "rb"), delimiter=b"\t")
    for line in reader:
        measurement = dict((label, cell) for label, cell in zip(columns, line))
        if measurement["sample"] == "JH0243_17_1":
            measurement["sample"] = "JH0243-17"
        elif measurement["sample"] == "JH0243_8_2":
            measurement["sample"] = "JH0243-8"
        elif measurement["sample"] == "JL91127":
            measurement["sample"] = "JL9112-7"
        datafile_found = False
        if acme_quirky_sample_name_pattern.match(measurement["sample"]):
            measurement["sample"] = measurement["sample"].replace("/", "-")
        match = acme_sample_pattern.match(measurement["sample"])
        if match:
            measurement["sample"] = normalize_acme_name(match.group(0))
            datafile_found = measurement["sample"] in acme_raw_files
            if datafile_found:
                measurement["datafile"] = acme_raw_files.pop(measurement["sample"])
                measurement["evaluated_datafile"] = acme_evaluated_files.pop(measurement["sample"], None)
        if not datafile_found:
            datafile = measurement["datafile"].lower()
            if number == 2:
                datafile += "_1"
                if not datafile in files:
                    datafile = datafile[:-2]
            if not datafile in files:
                # print u"File {0} not found.".format(measurement["datafile"])
                logging.error("File {0} not found.".format(measurement["datafile"]))
                continue
            try:
                measurement["datafile"] = guess_single_filename(files[datafile], measurement)
            except NoSinglePathFound as e:
                # print u"No single path for {0} found.  Possibilities: {1}".format(measurement["datafile"],
                #                                                                   u", ".join(e.paths))
                logging.error("No single path for {0} found.  Possibilities: {1}".format(
                        measurement["datafile"], ", ".join(e.paths)))
                continue
            consumed_filepaths.add(measurement["datafile"])
            evaluated_datafile = os.path.splitext(measurement["datafile"])[0] + "_kalk.rat"
            assert measurement["datafile"].startswith(root_dir)
            measurement["datafile"] = measurement["datafile"][len(root_dir):]
            measurement["evaluated_datafile"] = evaluated_datafile[len(root_dir):] if os.path.exists(evaluated_datafile) \
                else None
        if measurement["sample"] and measurement["manufacturer"]:
            if measurement["icrs"] == "46%-57%":
                measurement["icrs"] = "52"
            else:
                measurement["icrs"] = measurement["icrs"].rstrip("%")
            measurement["central_wavelength"] = measurement["central_wavelength"].partition(" ")[0]
            for fieldname in ["central_wavelength", "excitation_wavelength", "slit", "accumulation", "time", "laser_power",
                              "icrs"]:
                measurement[fieldname] = measurement[fieldname].replace(",", ".")
            if number == 2:
                if "makro" in measurement["objective"].lower():
                    measurement["setup"] = "macro"
                elif measurement["objective"].replace("-", "").strip():
                    measurement["setup"] = "micro"
            day, month, year = measurement["date"].split(".")
            day, month, year = int(day), int(month), int(year) + 2000
            seconds = measurements_on_day.get((year, month, day), 0)
            measurements_on_day[year, month, day] = seconds + 1
            date = datetime.datetime(year, month, day, 10, second=seconds)
            file_timestamp = datetime.datetime.fromtimestamp(
                os.path.getmtime(os.path.join(root_dir, measurement["datafile"])))
            if abs(file_timestamp.toordinal() - date.toordinal()) < 10:
                measurement["date"] = file_timestamp
                measurement["timestamp_inaccuracy"] = 0
            else:
                measurement["date"] = date
                print file_timestamp, date, measurement["datafile"]
                measurement["timestamp_inaccuracy"] = 3
            measurement["apparatus"] = number
            measurement["through_substrate"] = through_substrate_pattern.search(measurement["comments"])
            if not measurement["accumulation"]:
                measurement["accumulation"] = "-1"
                measurement["comments"] += "\n\nAkkumulation war in den Altdaten nicht angegeben."
            if not measurement["time"]:
                measurement["time"] = "-1"
                measurement["comments"] += "\n\nMesszeit war in den Altdaten nicht angegeben."
            if not measurement["laser_power"]:
                measurement["laser_power"] = "-1"
                measurement["comments"] += "\n\nLaserleistung war in den Altdaten nicht angegeben."
            if not measurement["central_wavelength"]:
                measurement["central_wavelength"] = "-1"
                measurement["comments"] += "\n\n$\\lambda_{\\mathrm{zentral}}$ war in den Altdaten nicht angegeben."
            if not measurement["excitation_wavelength"]:
                measurement["excitation_wavelength"] = "??"
                measurement["comments"] += "\n\n$\\lambda_{\\mathrm{Anregung}}$ war in den Altdaten nicht angegeben."
            if not measurement["slit"]:
                measurement["slit"] = "-1"
                measurement["comments"] += "\n\nSchlitzbreite war in den Altdaten nicht angegeben."
            measurement["operator"] = "f.koehler" if "florian" in measurement["datafile"].lower() else "m.huelsbeck"
            measurements.append(measurement)


def scan_wavelength(datafile):
    for wavelength in ["413", "488", "647", "752"]:
        if "/{0}/".format(wavelength) in datafile:
            return wavelength
    else:
        return "??"

savable_filename_pattern = re.compile(r"(?P<name>\d\d[A-Z]\d{1,4}|F\d{1,4}|\dL\d{1,4}|HA_?\d{1,3})", re.IGNORECASE)
corning_pattern = re.compile(r".*c\d$", re.IGNORECASE)
for datafile in filepaths - consumed_filepaths:
    filename = os.path.splitext(os.path.basename(datafile))[0]
    match = savable_filename_pattern.match(filename)
    if match:
        sample_name = match.group("name")
        if sample_name[1].lower() == "l":
            sample_name = "0" + sample_name
        if sample_name.lower().startswith("ha"):
            sample_name = "HA" + sample_name[3 if sample_name[2] == "_" else 2:]
        sample_name = sample_name.upper()
        try:
            year = int(sample_name[:2])
        except ValueError:
            year = None
        if year is None or 0 <= year <= 11:
            measurement = {}
            measurement["sample"] = sample_name
            measurement["date"] = datetime.datetime.fromtimestamp(os.path.getmtime(datafile))
            measurement["timestamp_inaccuracy"] = 0
            if sample_name[0] == "F" and measurement["date"] < datetime.datetime(1999, 1, 1):
                continue
            if measurement["date"] > datetime.datetime(2007, 1, 1):
                measurement["substrate"] = "Corning" if corning_pattern.match(filename) else ""
            else:
                measurement["substrate"] = ""
            measurement["apparatus"] = 2 if datafile[len(root_dir):].startswith("raman_2") else 1
            measurement["operator"] = "m.huelsbeck"
            measurement["comments"] = "Sehr alte Messung ohne elektronische Laborbuchdaten."
            measurement["datafile"] = datafile[len(root_dir):]
            evaluated_datafile = os.path.splitext(datafile)[0] + "_kalk.rat"
            measurement["evaluated_datafile"] = evaluated_datafile[len(root_dir):] if os.path.exists(evaluated_datafile) \
                else None
            measurement["excitation_wavelength"] = scan_wavelength(datafile)
            measurement["central_wavelength"] = -1
            measurement["slit"] = -1
            measurement["accumulation"] = -1
            measurement["time"] = -1
            measurement["laser_power"] = -1
            measurement["icrs"] = None
            measurement["through_substrate"] = False
            measurements.append(measurement)


for sample_name, raw_filepath in acme_raw_files.iteritems():
    measurement = {}
    measurement["sample"] = sample_name
    measurement["substrate"] = "Corning" if "c" in raw_filepath[-3:].lower() else ""
    measurement["date"] = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(root_dir, raw_filepath)))
    measurement["timestamp_inaccuracy"] = 0
    measurement["apparatus"] = 1
    measurement["operator"] = "m.huelsbeck"
    measurement["comments"] = "Messung ohne elektronische Laborbuchdaten."
    measurement["datafile"] = raw_filepath
    measurement["evaluated_datafile"] = acme_evaluated_files.get(sample_name)
    measurement["excitation_wavelength"] = "488"
    measurement["central_wavelength"] = 500
    measurement["slit"] = 150
    measurement["accumulation"] = -1
    measurement["time"] = -1
    measurement["laser_power"] = -1
    measurement["icrs"] = None
    measurement["through_substrate"] = False
    measurements.append(measurement)


print len(measurements), len(filter(lambda measurement: measurement["evaluated_datafile"], measurements)), \
    len(filter(lambda measurement: measurement["timestamp_inaccuracy"] != 0, measurements))
measurements.sort(key=lambda measurement: measurement["date"])

for measurement in measurements:
    print measurement["sample"], measurement["substrate"], measurement["date"]
    sample_id = get_or_create_sample(measurement["sample"], measurement["substrate"], measurement["date"],
                                     add_zno_warning=True)
    raman_measurement = RamanMeasurement(measurement["apparatus"])
    raman_measurement.sample_id = sample_id
    raman_measurement.operator = measurement["operator"]
    raman_measurement.timestamp = measurement["date"]
    raman_measurement.timestamp_inaccuracy = measurement["timestamp_inaccuracy"]
    raman_measurement.comments = measurement["comments"]
    raman_measurement.datafile = measurement["datafile"].decode("utf-8") if measurement["datafile"] else None
    raman_measurement.evaluated_datafile = \
        measurement["evaluated_datafile"].decode("utf-8") if measurement["evaluated_datafile"] else None
    raman_measurement.central_wavelength = measurement["central_wavelength"]
    raman_measurement.excitation_wavelength = measurement["excitation_wavelength"]
    raman_measurement.slit = measurement["slit"]
    raman_measurement.accumulation = measurement["accumulation"]
    raman_measurement.time = measurement["time"]
    raman_measurement.laser_power = measurement["laser_power"]
    raman_measurement.icrs = measurement["icrs"]
    raman_measurement.setup = measurement.get("setup", "unknown")
    raman_measurement.detector = "unknown"
    raman_measurement.grating = measurement.get("grating")
    raman_measurement.objective = measurement.get("objective")
    raman_measurement.through_substrate = measurement["through_substrate"]
    raman_measurement.submit()

logout()
