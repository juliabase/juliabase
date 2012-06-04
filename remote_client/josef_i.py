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

"""Crawler for PDS measurements.  This program is supposed to be started in
regular intervals.  It looks for new PDS measurements in ``PDS_tab.txt`` as
well as the file system and imports them into Chantal.

The basic strategy is this: First, we look for *changed* and *removed* PDS
measurements.  It doesn't matter whether they have been changed in the data
directories or in ``PDS_tab.txt``.  It even doesn't matter whether they have
been added or just edited.  Both means “changed”.

Then, we see which measurements are already in Chantal.  This way, we can
decide which measurements must be added and which just edited.  Those that have
been removed since the last run, but still exist in Chantal, trigger an error
email.

Things are slightly complicated by the fact that there are special files with
evaluated data.  When they are added or changed, the respective measurement
must be updated, too.  Moreover, it is not possible to calculate the path to
the measurement file from the PDS number *reliably*.  Therefore, I must create
a mapping which stores these paths.

You may use this crawler as the starting point for other crawlers.  Especially
logging and PID locking is typicaly for crawler cronjobs.
"""


from __future__ import absolute_import, unicode_literals

from chantal_remote import *
import chantal_remote
import os, os.path, re, codecs, datetime, logging, datetime
import cPickle as pickle

diff_file = "/home/chantal/crawler_data/pds.pickle"
measurement_data_root_dir = b"/mnt/T/Daten/"
assert os.path.isdir(measurement_data_root_dir)

with PIDLock("josef_i") as locked:
    if locked:
        chantal_remote.setup_logging(enable=True)
        my_logger = logging.FileHandler("/home/chantal/crawler_data/pds_measurement.log", "a")
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
        my_logger.setFormatter(formatter)
        my_logger.setLevel(logging.INFO)
        logging.getLogger("").addHandler(my_logger)

        logging.info("started crawling")

        import ConfigParser
        credentials = ConfigParser.SafeConfigParser()
        credentials.read(os.path.expanduser("/var/www/chantal.auth"))
        credentials = dict(credentials.items("DEFAULT"))

        root_dir = os.path.join(measurement_data_root_dir, b"pds/")
        database_path = os.path.join(measurement_data_root_dir, b"pdscpmdb/PDS_tab.txt")
        database_cache_path = "/home/chantal/crawler_data/pds_database.pickle"


        login(credentials["crawlers_login"], credentials["crawlers_password"])


        date_pattern = re.compile(r"#?(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{2,4})")
        def parse_date(datestring):
            match = date_pattern.match(datestring)
            if match:
                year = int(match.group("year"))
                if year < 100:
                    year = 1900 + year if year > 40 else 2000 + year
                return datetime.datetime(year, int(match.group("month")), int(match.group("day")))
            raise ValueError("Invalid date: {0}".format(datestring))


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

        def extract_comments(filename):
            """Extracts the measurements comments from the raw data file
            ``filename``.  This function also normalises the comments slightly
            and makes them ready for being used as Markdown texts.
            """
            lines = read_lines(filename)
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


        raw_filename_pattern = re.compile(r"pd(?P<number>\d+)\.dat", re.IGNORECASE)

        class PDSMeasurementInDatabase(object):
            """Class whose instances represent lines in ``PDS_tab.txt``.
            """

            def __init__(self, line):
                self.path, filename, self.date, self.sample_name, self.substrate, self.material, remarks = \
                    (item.strip() if item.strip() != "-" else "" for item in line.split(";", 6))
                if not self.sample_name:
                    self.sample_name = "unknown_name"
                match = raw_filename_pattern.match(filename)
                if match:
                    self.number = int(match.group("number"))
                else:
                    raise ValueError("Illegal filename: {0}".format(filename))
                self.date = parse_date(self.date)
                dirname = os.path.join(root_dir, os.path.basename(self.path[:-1].replace("\\", "/")))
                self.path = os.path.join(dirname, filename)
                if not os.path.exists(self.path):
                    raise ValueError("Non-existing filepath".format(self.path))
                self.comments = extract_comments(self.path)
                if not self.comments and remarks:
                    self.comments += remarks + "\n"
                if not self.comments.startswith(remarks) and remarks:
                    self.comments += "\nErgänzende Angaben in PDS-Datenbankdatei: {0}\n".format(remarks)

            def __eq__(self, other):
                if not isinstance(other, PDSMeasurementInDatabase):
                    return False
                else:
                    return self.path == other.path and self.date == other.date and \
                        self.sample_name == other.sample_name and \
                        self.substrate == other.substrate and self.comments == other.comments

            def __ne__(self, other):
                return not self.__eq__(other)


        raw_filename_pattern = re.compile(r"pd(?P<number>\d+)\.dat$", re.IGNORECASE)
        evaluated_filename_pattern = re.compile(r"a_pd(?P<number>\d+)(?P<suffix>_.+)\.dat$", re.IGNORECASE)
        phase_corrected_evaluated_filename_pattern = re.compile(r"a_ph_pd(?P<number>\d+)(?P<suffix>_.+)\.dat$",
                                                                re.IGNORECASE)


        changed, removed = set(), set()

        changed_files, removed_files = find_changed_files(root_dir, diff_file, r"pd\d+\.dat|a_(ph_)?pd\d+_.+\.dat")
        changed_raw = {}
        changed_evaluated = {}
        changed_phase_corrected_evaluated = {}
        removed = set()
        removed_evaluated = set()
        removed_phase_corrected_evaluated = set()

        for filepath in changed_files:
            match = raw_filename_pattern.search(filepath)
            if match:
                pds_number = int(match.group("number"))
                changed_raw[pds_number] = filepath
                changed.add(pds_number)
            else:
                match = evaluated_filename_pattern.search(filepath)
                if match:
                    pds_number = int(match.group("number"))
                    changed_evaluated[pds_number] = filepath
                    changed.add(pds_number)
                else:
                    pds_number = int(phase_corrected_evaluated_filename_pattern.search(filepath).group("number"))
                    changed_phase_corrected_evaluated[pds_number] = filepath
                    changed.add(pds_number)

        for filepath in removed_files:
            match = raw_filename_pattern.search(filepath)
            if match:
                pds_number = int(match.group("number"))
                removed.add(pds_number)
            else:
                match = evaluated_filename_pattern.search(filepath)
                if match:
                    pds_number = int(match.group("number"))
                    removed_evaluated.add(pds_number)
                else:
                    pds_number = int(phase_corrected_evaluated_filename_pattern.search(filepath).group("number"))
                    removed_evaluated.add(pds_number)


        try:
            old_pds_database = pickle.load(open(database_cache_path, "rb"))
        except IOError:
            old_pds_database = {}

        pds_database = {}
        illegal_lines = []
        for i, line in enumerate(codecs.open(database_path, encoding="cp1252")):
            try:
                measurement = PDSMeasurementInDatabase(line)
            except ValueError as error:
                illegal_lines.append(i + 1)
                logging.debug("illegal line {0}: {1}".format(i, error.args[0]))
            else:
                pds_database[measurement.number] = measurement
        if illegal_lines:
            illegal_lines = ", ".join(str(linenumber) for linenumber in illegal_lines)
            logging.error("illegal line(s) {0} in PDS_tab.txt".format(illegal_lines))


        for number, measurement in pds_database.iteritems():
            if measurement != old_pds_database.get(number):
                changed.add(number)
        removed |= set(old_pds_database) - set(pds_database)


        already_available_pds_numbers = PDSMeasurement.get_already_available_pds_numbers()

        to_be_edited = changed & already_available_pds_numbers
        to_be_added = changed - to_be_edited

        defered_filepaths = set()

        for number in sorted(to_be_added | to_be_edited):
            if number >= 90000:
                # Test measurement; to be ignored
                continue
            try:
                all_filepaths = set()
                try:
                    pds_measurement_in_db = pds_database[number]
                except KeyError:
                    send_error_mail("JOSEF I", "PDS-Messung fehlt", "Die PDS-Messung Nr. {0} wurde im Verzeichnis "
                                    "hinzugefügt,\nist aber nicht in der PDS-Datenbank-Übersichtsdatei.".format(number))
                    if pds_number in changed_raw:
                        all_filepaths.add(changed_raw[pds_number])
                    if pds_number in changed_evaluated:
                        all_filepaths.add(changed_evaluated[pds_number])
                    if pds_number in changed_phase_corrected_evaluated:
                        all_filepaths.add(changed_phase_corrected_evaluated[pds_number])
                    raise Exception("missing PDS #{0} in tab file".format(number))
                else:
                    sample_id = get_or_create_sample(pds_measurement_in_db.sample_name, pds_measurement_in_db.substrate,
                                                     pds_measurement_in_db.date, add_zno_warning=True)
                    if number in to_be_edited:
                        pds_measurement = PDSMeasurement(number)
                        pds_measurement.edit_description = "This was an automatic change by the crawler “JOSEF I”."
                        logging.info("#{0} is edited".format(number))
                    else:
                        pds_measurement = PDSMeasurement()
                        logging.info("#{0} is added".format(number))
                    pds_measurement.sample_id = sample_id
                    if "o.thimm" in pds_measurement_in_db.comments.lower():
                        pds_measurement.operator = "o.thimm"
                    else:
                        pds_measurement.operator = "j.klomfass"
                    if "pds2" in pds_measurement_in_db.comments.lower():
                        pds_measurement.apparatus = "pds2"
                    else:
                        pds_measurement.apparatus = "pds1"
                    pds_measurement.number = pds_measurement_in_db.number
                    if number in to_be_added:
                        file_date = datetime.datetime.fromtimestamp(os.path.getmtime(pds_measurement_in_db.path))
                        if file_date.year == pds_measurement_in_db.date.year and \
                                file_date.month == pds_measurement_in_db.date.month and \
                                file_date.day == pds_measurement_in_db.date.day:
                            pds_measurement.timestamp = file_date.strftime("%Y-%m-%d %H:%M:%S")
                            pds_measurement.timestamp_inaccuracy = 0
                        else:
                            pds_measurement.timestamp = pds_measurement_in_db.date.strftime("%Y-%m-%d %H:%M:%S")
                            pds_measurement.timestamp_inaccuracy = 3
                    else:
                        current_timestamp = pds_measurement.timestamp
                        if current_timestamp.year != pds_measurement_in_db.date.year or \
                                current_timestamp.month != pds_measurement_in_db.date.month or \
                                current_timestamp.day != pds_measurement_in_db.date.day:
                            pds_measurement.timestamp = pds_measurement_in_db.date.strftime("%Y-%m-%d %H:%M:%S")
                            pds_measurement.timestamp_inaccuracy = 3
                    pds_measurement.raw_datafile = pds_measurement_in_db.path[len(root_dir):]
                    all_filepaths.add(pds_measurement.raw_datafile)
                    if number in changed_evaluated:
                        pds_measurement.evaluated_datafile = changed_evaluated[number][len(root_dir):]
                        all_filepaths.add(pds_measurement.evaluated_datafile)
                        if number in to_be_edited:
                            pds_measurement.edit_description += \
                                "\nA PDS evaluation was added or changed.  (Possibly among other things.)"
                    elif number in removed_evaluated:
                        pds_measurement.evaluated_datafile = None
                    if number in changed_phase_corrected_evaluated:
                        pds_measurement.phase_corrected_evaluated_datafile = \
                            changed_phase_corrected_evaluated[number][len(root_dir):]
                        all_filepaths.add(pds_measurement.phase_corrected_evaluated_datafile)
                        if number in to_be_edited:
                            pds_measurement.edit_description += \
                                "\nA phase-corrected PDS evaluation was added or changed.  (Possibly among other things.)"
                    elif number in removed_phase_corrected_evaluated:
                        pds_measurement.phase_corrected_evaluated_datafile = None
                    pds_measurement.comments = pds_measurement_in_db.comments
                    pds_measurement.submit()
                    chantal_remote.connection.open("change_my_samples", {"remove": sample_id})
            except Exception as e:
                logging.error('Error at #{0}: {1}'.format(number, e))
                defered_filepaths |= all_filepaths
        defer_files(diff_file, defered_filepaths)
        logout()


        missing_numbers = removed & already_available_pds_numbers
        if missing_numbers:
            number_list = ", ".join(str(number) for number in missing_numbers)
            send_error_mail("JOSEF I", "PDS-Messung fehlt",
            """Die PDS-Messung(en) Nr. {0} wurde(n) im Verzeichnis und/oder in
der PDS-Datenbank-Übersichtsdatei gelöscht, aber sie ist
immer noch in der Chantal-Datenbank.""".format(number_list))
            logging.error("missing PDS measurement(s) {0} on disk or in the tab file".format(number_list))

        pickle.dump(pds_database, open(database_cache_path, "wb"), pickle.HIGHEST_PROTOCOL)

        logging.info("successfully ended crawling")
