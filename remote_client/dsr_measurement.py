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
import ConfigParser, codecs, datetime, logging, urllib, os.path, re, sys
from chantal_remote import PIDLock, login, logout, find_changed_files, normalize_sample_name, \
    get_or_create_sample, ChantalError, Structuring, connection, defer_files, DSRMeasurement, DSRIVData, DSRSpectralData
import chantal_remote


#log_path = b"/home/chantal/crawler_data/dsr_measurement.log"
#root_dir = b"/mnt/P/USER/w.reetz/DSR/Messwerte/"
#credentials_path = b"/var/www/chantal.auth"
#diff_file = b"/home/chantal/crawler_data/dsr.pickle"
log_path = b"/home/marvin/logs/dsr.log"
credentials_path = b"/home/marvin/chantal.auth"
#root_dir = b"/mnt/user_public/USER/w.reetz/DSR/Messwerte/"
diff_file = b"/home/marvin/logs/dsr.pickle"
root_dir = b"/home/marvin/Messwerte/"

class CrawlerError(Exception):
    pass


class CrawlerWarning(Exception):
    pass


import_legacy_data = len(sys.argv) > 1 and sys.argv[1] == "--import-legacy-data"

# all 'mother' objects, which are needed in this run, are stored in this dictionary.
# it is necessary to keep the HTTP connections to a minimum.
# the keys are the names of the files including the relative paths but without the file extensions.
dsr_measurement_by_filepath = {}

with PIDLock("dsr") as locked:
    if locked:

        chantal_remote.setup_logging(enable=True)
        my_logger = logging.FileHandler(log_path, "a")
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
        my_logger.setFormatter(formatter)
        my_logger.setLevel(logging.INFO)
        logging.getLogger("").addHandler(my_logger)

        credentials = ConfigParser.SafeConfigParser()
        credentials.read(credentials_path)
        credentials = dict(credentials.items("DEFAULT"))

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

        black_list = ["nt", "il", "be"]
        default_pattern = re.compile(r"(?P<name>\d\d[A-Za-z][-_]?"
                                      r"\d{1,4}[-/_]?\d{0,2}[a-zA-Z]?"
                                      r"[-/_]?[A-Za-z]*)(?P<cell>\d{1,2}).*$")
        acme1_sample_pattern = re.compile(r"(?P<name>(JH|SW|JG|JL|SL|TS|PW|mm|ST|MI)\d{4}-\d{1,2}.*?(_\d{1,2})?)"
                                        r"-(?P<cell>\d[abcd])(-(m\d+)?)?", re.IGNORECASE)
        acme2_sample_pattern = re.compile(r"(?P<name>(JH|SW|JG|JL|SL|TS|PW|mm|ST|MI|SK|MW)\d{4}-\d{1,2}.*?(_\d{1,2})?)"
                                        r"-(?P<cell>[abc]\d{1,2})(-m\d+)?", re.IGNORECASE)

        def get_sample_match(sample_name, file_name):
            sample_name_default_pattern_match = default_pattern.match(sample_name)
            sample_name_acme1_sample_pattern = acme1_sample_pattern.match(sample_name)
            sample_name_acme2_sample_pattern = acme2_sample_pattern.match(sample_name)
            file_name_default_pattern_match = default_pattern.match(file_name)
            file_name_acme1_sample_pattern = acme1_sample_pattern.match(file_name)
            file_name_acme2_sample_pattern = acme2_sample_pattern.match(file_name)

            if file_name_default_pattern_match:
                return "juelich standard", file_name_default_pattern_match
            elif file_name_acme1_sample_pattern:
                return "ACME 1", file_name_acme1_sample_pattern
            elif file_name_acme2_sample_pattern:
                return "ACME 2", file_name_acme2_sample_pattern
            elif sample_name_default_pattern_match:
                return "juelich standard", sample_name_default_pattern_match
            elif sample_name_acme1_sample_pattern:
                return "ACME 1", sample_name_acme1_sample_pattern
            elif sample_name_acme2_sample_pattern:
                return "ACME 2", sample_name_acme2_sample_pattern
            return "juelich standard", None


        def read_srp_file(data_file):
            dsr_measurement = DSRMeasurement()
            dsr_measurement.operator = "nobody"
            dsr_measurement.timestamp_inaccuracy = 1
            dsr_measurement.parameter_file = data_file[len(root_dir):].decode("utf-8")
            sample_name = ""
            file_name = ""
            date = ""
            time = ""
            for line in read_lines(data_file):
                if "name" in line.lower():
                    sample_name = line.split(":")[1].strip()
                if "file" in line.lower():
                    file_name = line.split(":")[1].strip()
                if "date" in line.lower():
                    date = line.split(":")[1].strip()
                if "time" in line.lower():
                    time = line.split(":", 1)[1].strip()
                    break
            layout_name, sample_name_match = get_sample_match(sample_name, file_name)
            if sample_name_match:
                dsr_measurement.cell_position = sample_name_match.group("cell")
                sample_name = sample_name_match.group("name")
            sample_name = sample_name.rstrip("/-_")
            try:
                day, month, year = date.split(".")
            except ValueError:
                day = date[0:2]
                month = date[2:4]
                year = date[4:]
            try:
                hour, minute = time.split(":")
            except ValueError:
                hour = time[0:2]
                minute = time[2:4]
            if int(year) < 100:
                year = 2000 + int(year)
            dsr_measurement.timestamp = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
            return sample_name, layout_name, dsr_measurement


        logging.info("started crawling")
        login(credentials["crawlers_login"], credentials["crawlers_password"], testserver=True)

        defered_filepaths = set()

        changed, removed = find_changed_files(root_dir, diff_file, r".+\.SRP$")
        for data_file in changed:
            sample_id = None
            try:
                sample_name, layout_name, dsr_measurement = read_srp_file(data_file)
                sample_name = normalize_sample_name(sample_name)["name"]
                if any(sample_name.lower().startswith(s) for s in black_list):
                    filename = os.path.relpath(data_file, root_dir)
                    raise CrawlerWarning('"{0}"; ignored'.format(filename))
                sample_id = get_or_create_sample(sample_name, None, dsr_measurement.timestamp,
                                                 dsr_measurement.timestamp_inaccuracy, create=import_legacy_data)
                if not sample_id:
                    raise CrawlerWarning('"{0}" not found in the database; ignored'.format(sample_name))
                dsr_measurement.sample_id = sample_id
                try:
                    process_id = connection.open("dsr_measurements/by_filepath/?filepath={0}".format(
                                                 urllib.quote_plus(dsr_measurement.parameter_file.encode("utf-8"))))
                except ChantalError as e:
                    if e.error_code != 2:
                        raise
                else:
                    dsr_measurement.process_id = process_id
                    dsr_measurement.existing = True
                    dsr_measurement.edit_description = "Automatically edited by dsr crawler."
                dsr_measurement_by_filepath[dsr_measurement.parameter_file[:dsr_measurement.parameter_file.rfind(".")]] = \
                    dsr_measurement
                structuring = connection.open("structurings/by_sample/{0}?timestamp={1}".format(
                        urllib.quote_plus(str(sample_id)), urllib.quote_plus(str(dsr_measurement.timestamp))))
                if not structuring:
                    logging.info("create structuring for sample {sample}".format(sample=sample_name))
                    structuring = Structuring()
                    structuring.sample_id = sample_id
                    structuring.process_id = None
                    # FixMe: As long as editing structurings is not possible.
                    structuring.operator = "nobody"
                    structuring.timestamp = dsr_measurement.timestamp - datetime.timedelta(seconds=1)
                    structuring.timestamp_inaccuracy = dsr_measurement.timestamp_inaccuracy
                    structuring.comments = "automatically generated"
                    structuring.layout = layout_name
                    logging.debug("set structuring layout to {layout}".format(layout=structuring.layout))
                    structuring.submit()
            except CrawlerWarning as e:
                relative_path = os.path.relpath(data_file, root_dir)
                logging.warning('Warning at "{0}": {1}'.format(relative_path.decode("utf-8"), e))
                defered_filepaths.add(relative_path)
            except Exception as e:
                relative_path = os.path.relpath(data_file, root_dir)
                logging.error('Error at "{0}": {1}'.format(relative_path.decode("utf-8"), e))
                defered_filepaths.add(relative_path)
            finally:
                if sample_id:
                    chantal_remote.connection.open("change_my_samples", {"remove": sample_id})

        changed, removed = find_changed_files(root_dir, diff_file, r".+\.[IS]\d\d$")
        for data_file in changed:
            data_file = data_file.decode("utf-8")
            relative_path = os.path.relpath(data_file, root_dir)
            dsr_measurement = dsr_measurement_by_filepath.get(relative_path[:relative_path.rfind(".")])
            try:
                if not dsr_measurement:
                    try:
                        process_id = connection.open("dsr_measurements/by_filepath/?filepath=" +
                            urllib.quote_plus(re.sub(r"\.[IS]\d\d", ".SRP", relative_path).encode("utf-8")))
                    except ChantalError as e:
                        if e.error_code != 2:
                            raise
                    else:
                        dsr_measurement = DSRMeasurement(process_id)
                        dsr_measurement_by_filepath[relative_path[:relative_path.rfind(".")]] = dsr_measurement
                if dsr_measurement:
                    if "i" in data_file[data_file.rfind("."):].lower():
                        dsr_data = DSRIVData()
                        dsr_data.iv_data_file = data_file[len(root_dir):]
                        dsr_measurement.iv_data.add(dsr_data)
                        logging.info("Adding {0} to {1}.".format(dsr_data.iv_data_file, dsr_measurement.parameter_file))
                    elif "s" in data_file[data_file.rfind("."):].lower():
                        dsr_data = DSRSpectralData()
                        dsr_data.spectral_data_file = data_file[len(root_dir):]
                        dsr_measurement.spectral_data.add(dsr_data)
                        logging.info("Adding {0} to {1}.".format(dsr_data.spectral_data_file, dsr_measurement.parameter_file))

            except Exception as e:
                relative_path = os.path.relpath(data_file, root_dir)
                logging.error('Error at "{0}": {1}'.format(relative_path, e))
                defered_filepaths.add(relative_path)

        for measurement in dsr_measurement_by_filepath.itervalues():
            try:
                measurement.submit()
                logging.info("Submit {0}".format(measurement.parameter_file))
            except CrawlerWarning as e:
                logging.warning('Warning at "{0}": {1}'.format(measurement.parameter_file, e))
            except Exception as e:
                logging.error('Error at "{0}": {1}'.format(measurement.parameter_file, e))


        defer_files(diff_file, defered_filepaths)
        logout()
