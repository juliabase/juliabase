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

"""Crawler for all three conductivity apparatuses.  See the PDS crawler
``josef_i.py`` for further information.
"""


from __future__ import unicode_literals
import codecs, datetime, logging, os.path, re, sys, urllib2
from chantal_remote import ConductivityMeasurementSet, Sample, PIDLock, login, logout, find_changed_files, \
    get_or_create_sample, ChantalError, ConductivityMeasurement, defer_files, connection, setup_logging
import ConfigParser


import_legacy_data = len(sys.argv) > 1 and sys.argv[1] == "--import-legacy-data"

measurement_data_root_dir = b"/mnt/T/Daten/"
assert os.path.isdir(measurement_data_root_dir)


with PIDLock("conductivity") as locked:
    if locked:
        setup_logging(enable=True)
        my_logger = logging.FileHandler("/home/chantal/crawler_data/conductivity_measurement_set.log", "a")
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
        my_logger.setFormatter(formatter)
        my_logger.setLevel(logging.INFO)
        logging.getLogger("").addHandler(my_logger)

        credentials = ConfigParser.SafeConfigParser()
        credentials.read("/var/www/chantal.auth")
        credentials = dict(credentials.items("DEFAULT"))

        root_dirs = (("conductivity0", os.path.join(measurement_data_root_dir, b"conductance0/Conductance_daten/")),
                     ("conductivity1", os.path.join(measurement_data_root_dir, b"conductance1/Conductance_daten/")),
                     ("conductivity2", os.path.join(measurement_data_root_dir, b"conductance2/Conductance_daten/")))

        map_apparatus = {"conductance0": "conductivity0",
                         "conductance1": "conductivity1",
                         "conductance2": "conductivity2"}

        date_pattern = re.compile(r"#?(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2,4})")
        photo_measurement_pattern = re.compile(r"photo|foto|hell|light|bright|licht", re.IGNORECASE)
        def parse_date(datestring):
            match = date_pattern.match(datestring)
            year = int(match.group("year"))
            if year < 100:
                year = 1900 + year if year > 40 else 2000 + year
            return datetime.datetime(year, int(match.group("month")), int(match.group("day")))

        def read_lines(filename):
            """Reads the lines of ``filename``, trying different encodings.
            The files have been created over a long period of time, so DOS as
            well as Windows encodings may have been used.
            """
            try:
                return codecs.open(filename, encoding="cp1252").readlines()
            except UnicodeDecodeError:
                try:
                    return codecs.open(filename, encoding="cp437").readlines()
                except UnicodeDecodeError:
                    return open(filename).readlines()

        def extract_comments(lines):
            """Extracts the measurements comments from the given
            ``lines``-list.  This function also normalises the comments
            slightly and makes them ready for being used as Markdown texts.
            """
            comment_lines = []
            for i, line in enumerate(lines[:20]):
                linenumber = i + 1
                line = line.strip()
                if line.startswith("BEGIN") or (i + 1 < len(lines) and lines[i + 1].startswith("BEGIN")):
                    break
                if linenumber >= 5:
                    comment_lines.append(line)
            while comment_lines and not comment_lines[-1]:
                del comment_lines[-1]
            if comment_lines and not (len(comment_lines) == 1 and comment_lines[0] == "-"):
                comments = "  \n".join(comment_lines) + "\n"
            else:
                comments = ""
            while "\n  \n" in comments:
                comments = comments.replace("\n  \n", "\n")
            return comments

        def get_next_measurement_number(measurements):
            next_number = 1
            if measurements:
                numbers = []
                for measurement in measurements:
                    numbers.append(measurement.number)
                next_number = max(numbers) + 1
            return next_number

        pathname_pattern = re.compile(r"Daten/(?P<apparatus>conductance[0-2])/")
        temper_pattern = re.compile(r"(?P<temperature>\d{3})\s*k\s*/\s*(?P<time>\d{1,3})\s*m(in){0,1}", re.IGNORECASE)
        temper_pattern2 = re.compile(r"(?P<temperature>\d{3})/(?P<time>\d{1,3})")
        temper_pattern3 = re.compile(r"nach tempern|n\. tempern|aft.*\bann", re.IGNORECASE)
        air_pattern = re.compile(r"air|luft", re.IGNORECASE)
        class ConductivityFileInformations(object):
            """Collects the informations from the conductivity data files.
            """

            def __init__(self, filepath):
                self.info_dict = {}
                self.path = filepath
                lines = read_lines(filepath)
                if not lines:
                    raise EOFError
                if ":" in lines[1]:
                    self.sample_name = lines[1].split(":")[1].strip()
                else:
                    self.sample_name = lines[1].strip()
                self.info_dict["data file"] = os.path.relpath(self.path, measurement_data_root_dir).decode("utf-8")

                dateline = lines[0].strip()
                if dateline.startswith("Datum"):
                    timestamp = parse_date(lines[0].partition(":")[2].strip())
                    timestamp_inaccuracy = 3
                else:
                    date, __, time = dateline.partition(" ")
                    if date:
                        timestamp = parse_date(date)
                        timestamp_inaccuracy = 3
                        if time:
                            hour, minute, second = time.split(":")
                            timestamp = timestamp.replace(hour=int(hour), minute=int(minute), second=int(second))
                            timestamp_inaccuracy = 0
                    else:
                        timestamp = None
                if not timestamp or timestamp_inaccuracy == 3:
                    try:
                        file_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                        file_timestamp = file_timestamp.replace(microsecond=0)
                    except OSError:
                        pass
                    else:
                        if not timestamp or file_timestamp.date() == timestamp.date():
                            timestamp = file_timestamp
                            timestamp_inaccuracy = 0
                if timestamp_inaccuracy == 3:
                    timestamp = timestamp.replace(hour=14, minute=0, second=0)
                self.timestamp, self.timestamp_inaccuracy = timestamp, timestamp_inaccuracy

                self.substrate = lines[2].split(":")[1].strip() if ":" in lines[2] else lines[2].strip()
                self.username = lines[6].strip()
                self.info_dict["comments"] = extract_comments(lines)
                self.info_dict["temperature"] = ""
                self.info_dict["temper time"] = ""
                match = temper_pattern.search(self.info_dict["comments"])
                if not match and temper_pattern3.search(lines[5]):
                    self.info_dict["temperature"] = "440"
                    self.info_dict["temper time"] = "30"
                elif match:
                    self.info_dict["temperature"] = match.group("temperature").replace(" ", "")
                    self.info_dict["temper time"] = match.group("time").replace(" ", "")
                elif self.timestamp >= datetime.datetime(2011, 3, 25) and ";" in lines[7]:
                    match = temper_pattern2.match(lines[7].split(";")[1])
                    if match:
                        self.info_dict["temperature"] = match.group("temperature")
                        self.info_dict["temper time"] = match.group("time")
                if photo_measurement_pattern.search(self.info_dict["comments"]):
                    self.info_dict["light conditions"] = "photo"
                else:
                    self.info_dict["light conditions"] = "dark"
                self.info_dict["comments"] = unicode(lines[4].strip())
                self.info_dict["apparatus"] = map_apparatus[pathname_pattern.search(filepath).group("apparatus")]
                try:
                    self.info_dict["in vacuum"] = not air_pattern.search(lines[7] + lines[4])
                except IndexError:
                    self.info_dict["in vacuum"] = True

            def __lt__(self, other):
                if self.timestamp != other.timestamp:
                    return self.timestamp < other.timestamp
                else:
                    return self.path < other.path


        logging.info("started crawling")
        login(credentials["crawlers_login"], credentials["crawlers_password"])

        for apparatus, root_dir in root_dirs:
            diff_file = "/home/chantal/crawler_data/{0}.pickle".format(apparatus)
            changed, __ = find_changed_files(root_dir, diff_file, r"[dfikln]{2,3}\d+\.dat")
            conductivity_files = []
            file_info = None
            for filepath in changed:
                try:
                    lines = read_lines(filepath)
                except IOError:
                    logging.error("could not access {0}".format(filepath))
                    continue
                else:
                    try:
                        if "test" in lines[1].lower() or "tes" in lines[1].lower():
                            continue
                    except IndexError:
                        pass
                try:
                    conductivity_files.append(ConductivityFileInformations(filepath))
                except EOFError:
                    logging.error("{0} is empty".format(filepath))
                    continue
                except ValueError as e:
                    logging.error("{0} at {1}".format(e, filepath))
                    continue
            defered_filepaths = set()

            conductivity_files.sort()
            current_day = None
            last_timestamp = None
            for conductivity_file in conductivity_files:
                timestamp, timestamp_inaccuracy = conductivity_file.timestamp, conductivity_file.timestamp_inaccuracy
                if timestamp.toordinal() != current_day:
                    current_day = timestamp.toordinal()
                    current_day_index = 1
                if timestamp == last_timestamp:
                    conductivity_file.timestamp += datetime.timedelta(seconds=current_day_index)
                    current_day_index += 1
                last_timestamp = timestamp
            conductivity_files.sort()

            for conductivity_file in conductivity_files:
                sample_name = conductivity_file.sample_name
                if not sample_name:
                    logging.warning("no sample name in {0}".format(conductivity_file.path.decode("utf-8")))
                    defered_filepaths.add(os.path.relpath(conductivity_file.path, root_dir))
                    continue
                timestamp, timestamp_inaccuracy = conductivity_file.timestamp, conductivity_file.timestamp_inaccuracy
                try:
                    sample_id = get_or_create_sample(sample_name, conductivity_file.substrate, timestamp,
                                                     timestamp_inaccuracy, create=import_legacy_data)

                except ChantalError as e:
                    logging.error("get_or_create_sample Error {0} with sample {1} in {2}".format(
                            e, sample_name, conductivity_file.info_dict["data file"]))
                    defered_filepaths.add(os.path.relpath(conductivity_file.path, root_dir))
                    continue
                if not sample_id:
                    relative_path = os.path.relpath(conductivity_file.path, root_dir)
                    logging.warning('"{0}" not found in the database; ignored file {1}'.format(
                            sample_name, relative_path.decode("utf-8")))
                    defered_filepaths.add(relative_path)
                    continue

                try:
                    conductivity_measurement_set = ConductivityMeasurementSet.by_timestamp(
                        conductivity_file.info_dict["apparatus"], sample_id, timestamp)
                except ChantalError:
                    logging.error("Changes in {0} ignored because later measurements already exist.".format(
                            conductivity_file.info_dict["data file"]))
                    connection.open("change_my_samples", {"remove": sample_id})
                    continue

                if conductivity_measurement_set.existing:
                    result_msg = "{filename} was added to conductivity set #{pk}"\
                      .format(filename=conductivity_file.info_dict["data file"], pk=conductivity_measurement_set.id)
                else:
                    conductivity_measurement_set.sample_id = sample_id
                    conductivity_measurement_set.apparatus = conductivity_file.info_dict["apparatus"]
                    conductivity_measurement_set.comments = ""
                    conductivity_measurement_set.operator = conductivity_file.username or "nobody"
                    if conductivity_measurement_set.operator in ["KENNLINIE", "DUNKELLEIT", "INT_CONDUCT",
                                                                 "LEITF\xc4HIGKEIT"]:
                        conductivity_measurement_set.operator = "nobody"
                    result_msg = "New conductivity set was added to sample {0}".format(sample_name)
                conductivity_measurement_set.edit_description = result_msg + \
                    " by the crawler “conductivity2chantal”."

                conductivity_file.info_dict["number"] = get_next_measurement_number(
                    conductivity_measurement_set.measurements)
                single_conductivity_measurement = ConductivityMeasurement()
                single_conductivity_measurement.number = conductivity_file.info_dict["number"]
                single_conductivity_measurement.filepath = conductivity_file.info_dict["data file"]
                single_conductivity_measurement.tempering_time = conductivity_file.info_dict["temper time"]
                single_conductivity_measurement.tempering_temperature = conductivity_file.info_dict["temperature"]
                single_conductivity_measurement.in_vacuum = conductivity_file.info_dict["in vacuum"]
                single_conductivity_measurement.light = conductivity_file.info_dict["light conditions"]
                single_conductivity_measurement.timestamp = timestamp
                single_conductivity_measurement.timestamp_inaccuracy = timestamp_inaccuracy
                single_conductivity_measurement.comments = conductivity_file.info_dict["comments"]

                conductivity_measurement_set.append_single_measurement(single_conductivity_measurement)

                try:
                    conductivity_measurement_set.submit()
                except Exception as e:
                    logging.error(unicode(e))
                    defered_filepaths.add(os.path.relpath(conductivity_file.path, root_dir))
                else:
                    logging.info(result_msg)
                connection.open("change_my_samples", {"remove": sample_id})
            defer_files(diff_file, defered_filepaths)
        logout()
