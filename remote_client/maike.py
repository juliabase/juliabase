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
from chantal_remote import Sample, SolarsimulatorDarkMeasurement, SolarsimulatorPhotoMeasurement, \
    PhotoCellMeasurement, DarkCellMeasurement, PIDLock, login, logout, find_changed_files, \
    get_or_create_sample, ChantalError, Structuring, connection, defer_files
import chantal_remote

"""The MAIKE crawler.  It can import measurements with standard Jülich layout
and those of non-sstandard layouts.  It can deal with changed files, even if
the sample name was changed.  It cannot deal, however, with changed sample
names in non-standard layout file if the former name also does exist in the
database.

It cannot guarantee that the structuring process is before all MAIKE
measurements in all cases.  This can only be a problem if a sample name was
changed.
"""

log_path = b"/home/chantal/crawler_data/solarsimulator_photo_measurement.log"
credentials_path = b"/var/www/chantal.auth"
root_dir = b"/mnt/P/LABOR USER/maike_user/ascii files/"
diff_file = b"/home/chantal/crawler_data/maike.pickle"
#log_path = b"/home/marvin/logs/maike.log"
#credentials_path = b"/home/marvin/chantal.auth"
#root_dir = b"/mnt/user_public/LABOR USER/maike_user/ascii files/"
#diff_file = b"/home/marvin/logs/maike.pickle"
#root_dir = "/home/chantal/maike_messungen/"


import_legacy_data = len(sys.argv) > 1 and sys.argv[1] == "--import-legacy-data"


class CrawlerError(Exception):
    pass


class CrawlerWarning(Exception):
    pass


assert os.path.isdir(root_dir)


with PIDLock("maike") as locked:
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

        map_month = {"jan": 1,
                   "feb": 2,
                   "mar": 3,
                   "mär": 3,
                   "apr": 4,
                   "may": 5,
                   "mai": 5,
                   "jun": 6,
                   "jul": 7,
                   "aug": 8,
                   "aub": 8,
                   "sep": 9,
                   "oct": 10,
                   "okt": 10,
                   "nov": 11,
                   "dec": 12,
                   "dez": 12}

        date_pattern = re.compile(r"#?(?P<day>\d{1,2})\s(?P<month>[a-zA-Z]{3})\s(?P<year>\d{2,4})")
        def parse_date(datestring):
            match = date_pattern.match(datestring)
            if match:
                year = int(match.group("year"))
                if year < 100:
                    year = 1900 + year if year > 40 else 2000 + year
                return datetime.datetime(year, map_month[match.group("month").lower()], int(match.group("day")))


        map_username_to_login_name = {"A. Gerber": "a.gerber",
                                      "Andreas Lambertz": "a.lambertz",
                                      "Andreas Mück": "a.mueck",
                                      "Arjan Flikweert": "a.flikweert",
                                      "Flikweert": "a.flikweert",
                                      "Björn Gootoonk": "b.grootoonk",
                                      "Björn Gootoonkl": "b.grootoonk",
                                      "Björn Grootoon": "b.grootoonk",
                                      "Björn GRootoonk": "b.grootoonk",
                                      "Björn Grootoonk": "b.grootoonk",
                                      "Brigitte Zwaygardt": "b.zwaygardt",
                                      "C.Zahren": "c.zahren",
                                      "CZ": "c.zahren",
                                      "Zahren": "c.zahren",
                                      "Carsten Grates": "c.grates",
                                      "Carsten Grtes": "c.grates",
                                      "Caten Grates": "c.grates",
                                      "Chen Tao": "t.chen",
                                      "Tao Chen": "t.chen",
                                      "Daid Wippler": "d.wippler",
                                      "DAVID WIPPLER": "d.wippler",
                                      "David Wippler": "d.wippler",
                                      "Dzmitry Hrunsky": "d.hrunsky",
                                      "E.Moulin": "e.moulin",
                                      "Etienne": "e.moulin",
                                      "Etienne Moulim": "e.moulin",
                                      "Etienne Moulin": "e.moulin",
                                      "F. Einsele": "f.einsele",
                                      "Florian Einsele": "f.einsele",
                                      "franz birmans": "f.birmans",
                                      "Franz Birmans": "f.birmans",
                                      "G. Schöpe": "g.schoepe",
                                      "Gunnar Schöpe": "g.schoepe",
                                      "Gabrielle Jost": "g.jost",
                                      "Hongbing": "__hongbing",
                                      "J Kroll": "j.kroll",
                                      "J. Kroll": "j.kroll",
                                      "J.Kroll": "j.kroll",
                                      "j.Kroll": "j.kroll",
                                      "J.Kroll   Tel. 4588": "j.kroll",
                                      "J.Kroll Tel 4588": "j.kroll",
                                      "J.Kroll Tel 4855": "j.kroll",
                                      "Jani Kroll": "j.kroll",
                                      "Janis Kroll": "j.kroll",
                                      "janis Kroll": "j.kroll",
                                      "janis kroll": "j.kroll",
                                      "Janis.Kroll": "j.kroll",
                                      "JK": "j.kroll",
                                      "jk": "j.kroll",
                                      "Kroll": "j.kroll",
                                      "kroll": "j.kroll",
                                      "Kroll Janis": "j.kroll",
                                      "Jan Hemani": "j.hermani",
                                      "Jan Hermani": "j.hermani",
                                      "Jan Wördenweber": "j.woerdenweber",
                                      "j.wordenweber": "j.woerdenweber",
                                      "Joachim Kirchhoff": "j.kirchhoff",
                                      "Kirchhoff": "j.kirchhoff",
                                      "kirchhoff": "j.kirchhoff",
                                      "Joachim Schlang": "j.schlang",
                                      "Jonas": "j.noll",
                                      "Jonas Noll": "j.noll",
                                      "Jose Rodrigez": "j.rodriguez",
                                      "Jose Rodriguez": "j.rodriguez",
                                      "k.ding": "k.ding",
                                      "K.Ding": "k.ding",
                                      "Kaining": "k.ding",
                                      "Kaining Din": "k.ding",
                                      "Kaining ding": "k.ding",
                                      "Kaining Ding": "k.ding",
                                      "Katharina Baumgartner": "k.baumgartner",
                                      "Kilper": "t.kilper",
                                      "Kilpr": "t.kilper",
                                      "Thilo Kilper": "t.kilper",
                                      "Lihong": "l.xiao",
                                      "Xiaodan": "l.xiao",
                                      "Marek Warzecha": "m.warzecha",
                                      "Marzano": "__marzano",
                                      "Matthias Meier": "ma.meier",
                                      "Matthias Meir": "ma.meier",
                                      "Meier": "ma.meier",
                                      "Micelle Bosquet": "m.bosquet",
                                      "Michelle Boquet": "m.bosquet",
                                      "Michelle Bosquet": "m.bosquet",
                                      "Michlle Bosquet": "m.bosquet",
                                      "Mihelle Bosquet": "m.bosquet",
                                      "Muhammad Tayyib": "m.tayyib",
                                      "Paul Wöbkenberg": "p_woebkenberg",
                                      "Ralf Schmitz": "ra.schmitz",
                                      "Rebecca v.Aubel": "r.van.aubel",
                                      "Rebecca van Aubel": "r.van.aubel",
                                      "van Aubel": "r.van.aubel",
                                      "R. van Aubel": "r.van.aubel",
                                      "Sandra Schicho": "s.schicho",
                                      "sascha": "s.pust",
                                      "Sascha": "s.pust",
                                      "Sascha Pust": "s.pust",
                                      "Stefan Haas": "st.haas",
                                      "Muthmann": "s.muthmann",
                                      "Stefan Muthmann": "s.muthmann",
                                      "Stephan Micardann": "s.michard",
                                      "Stephan Michard": "s.michard",
                                      "Stephan Michard\x1b": "s.michard",
                                      "Stephan Michardnn": "s.michard",
                                      "Stephn Michard": "s.michard",
                                      "Stphan Michard": "s.michard",
                                      "Thomas Zimmermann": "t.zimmermann",
                                      "Torsten Bronger": "t.bronger",
                                      "Tsvetelina Merdzhanova": "t.merdzhanova",
                                      "V. Smirnov": "v.smirnov",
                                      "Vladimir Smirnov": "v.smirnov",
                                      "Wajiao": "w.boettler",
                                      "Wajiao Böttler": "w.boettler",
                                      "Waniao": "w.boettler",
                                      "Wanjiao": "w.boettler",
                                      "wanjiao": "w.boettler",
                                      "Wanjiao Böttler": "w.boettler",
                                      "Wanjiaoo": "w.boettler",
                                      "Wendi": "w.zhang",
                                      "Wendi zhang": "w.zhang",
                                      "Wendi Zhang": "w.zhang",
                                      "Wilfried": "w.reetz",
                                      "WR": "w.reetz",
                                      "wr": "w.reetz",
                                      "Ü.Dagkaldiran": "u_dagkaldiran",
                                      "Ümit Dagkaldiran": "u_dagkaldiran",
                                      "u.dagkaldiran": "u_dagkaldiran", }

        def normalize_username(username):
            login_name = map_username_to_login_name.get(username)
            if not login_name:
                login_name = username if connection.primary_keys["users"].get(username) \
                    else "nobody"
            return login_name

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

        def extract_data_from_file(filepath):
            """

            :Parameters:
              - `filepath`: the full path to the datafile

            :type filepath: str
            """
            def warn_irradiance():
                logging.warning('In "{filename}": The file extension doesn\'t match the format of the '
                                'data table.  Set to "{irradiance}".'.
                                format(filename=filename, irradiance=irradiance))
            logging.debug("extract {filename}".format(filename=filepath.decode("utf-8")))
            lines = read_lines(filepath)
            if len(lines) < 31:
                raise CrawlerError("The datafile doesn't match the expecting format.")
            first_table = second_table = False
            cell_index = -3
            active = False
            cell = None
            filename = filepath[len(root_dir):].decode("utf-8")
            irradiance = ""
            if filename.endswith(".asw"):
                irradiance = "AM1.5"
            elif filename.endswith(".aso"):
                irradiance = "OG590"
            elif filename.endswith(".asb"):
                irradiance = "BG7"
            elif filename.endswith(".asd"):
                irradiance = "dark"
            if irradiance == "dark" and not "N_diode" in lines[30]:
                irradiance = "AM1.5"
                warn_irradiance()
            elif irradiance in ["AM1.5", "OG590", "BG7"] and not "Flaeche/cm^2" in lines[30]:
                irradiance = "dark"
                warn_irradiance()
            solarsimulator_measurement = SolarsimulatorDarkMeasurement() if irradiance == "dark" \
                else SolarsimulatorPhotoMeasurement()
            solarsimulator_measurement.irradiance = irradiance
            if not lines[3].startswith(";"):
                raise CrawlerError("The datafile doesn't match the expecting format.")
            try:
                solarsimulator_measurement.timestamp = \
                    datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).replace(microsecond=0)
                solarsimulator_measurement.timestamp_inaccuracy = 0
            except OSError:
                solarsimulator_measurement.timestamp = None
            for line_number, line in enumerate(lines):
                # FixMe: The date must be changed from 1.1.2100 to the date
                # when the new MAIKE program is used (with hopefully *reliable*
                # timestamps in the file header).
                ignore_timestamp_in_file_header = not solarsimulator_measurement.timestamp or \
                    solarsimulator_measurement.timestamp < datetime.datetime(2100, 1, 1)
                if line.startswith(";Messdatum") and line_number < 10:
                    timestamp = parse_date(line.strip().split(",")[1])
                    if timestamp and (not solarsimulator_measurement.timestamp or
                                      solarsimulator_measurement.timestamp.date() != timestamp.date()):
                        if not ignore_timestamp_in_file_header:
                            timestamp += datetime.timedelta(hours=14)
                            solarsimulator_measurement.timestamp = timestamp
                            solarsimulator_measurement.timestamp_inaccuracy = 3
                        else:
                            logging.warning('In "{filename}": The date in file doesn\'t match the file\'s timestamp.'
                                            '  Took the file\'s timestamp.'.format(filename=filename))
                elif line.startswith(";Name"):
                    solarsimulator_measurement.operator = normalize_username(line.strip().split(",")[1])
                elif line.startswith(";Probenbezeichnung"):
                    sample_name = line.strip().split(",", 1)[1] or "unknown"
                elif line.startswith(";Bemerkung"):
                    solarsimulator_measurement.comments = "{0}\n{1}\n{2}".format(line.strip().split(",")[1],
                                                               lines[line_number + 1].strip().split(",")[1],
                                                               lines[line_number + 2].strip().split(",")[1])
                elif line.startswith(";Temperatur"):
                    solarsimulator_measurement.temperature = float(line.strip().split(",")[1])
                elif line.startswith(";Datentabelle"):
                    first_table = True
                if first_table and cell_index > 0:
                    if not line.strip().endswith(5 * ", 0"):
                        active = True
                        cell = None
                        values = line.split(",")
                        if irradiance == "dark":
                            cell = DarkCellMeasurement()
                            cell.position = values[0].strip()
                            cell.cell_index = int(values[0])
                            cell.n_diode, cell.i_0 = float(values[1]), float(values[2])
                        else:
                            cell = PhotoCellMeasurement()
                            cell.position = values[0].strip()
                            cell.cell_index = int(values[0])
                            cell.area, cell.eta, cell.p_max, cell.ff, cell.voc, cell.isc, cell.rs, cell.rsh, \
                                cell.corr_fact = [float(value) for value in values[1:]]
                            if cell.area:
                                cell.isc /= cell.area
                            else:
                                cell.isc = None
                        cell.data_file = filename
                        solarsimulator_measurement.cells[cell.position] = cell
                if first_table:
                    cell_index += 1
                    if cell_index == 37:
                        first_table = False
                if line.startswith(";U/V") and not active:
                    second_table = True
                elif second_table:
                    if not line.strip().endswith(36 * ", 0"):
                        for cell_index, value in enumerate(line.strip().split(',')[1:]):
                            cell_index += 1
                            if value != " 0":
                                if irradiance == "dark":
                                    cell = DarkCellMeasurement()
                                    cell.position = cell_index
                                    cell.cell_index = cell_index
                                    cell.n_diode = cell.i_0 = None
                                else:
                                    cell = PhotoCellMeasurement()
                                    cell.position = cell_index
                                    cell.cell_index = cell_index
                                    cell.area = cell.eta = cell.p_max = cell.ff = cell.voc = cell.isc = cell.rs = \
                                        cell.rsh = cell.corr_fact = None
                                cell.data_file = filename
                                solarsimulator_measurement.cells[cell.position] = cell
                                active = True
                if active and not first_table:
                    break
            if not solarsimulator_measurement.timestamp:
                raise CrawlerError("Couldn't determine timestamp for datafile.")
            if not solarsimulator_measurement.cells:
                raise CrawlerError("The datafile didn't contain measured cells.")
            return solarsimulator_measurement, sample_name, filename


        logging.info("started crawling")
        login(credentials["crawlers_login"], credentials["crawlers_password"], testserver=False)
        pattern_suffix = r"(?:__\d{6}_\d{6})?\.as[wobd]$"

        acme1_file_pattern = re.compile(r"(JH|SW|JG|JL|SL|TS|PW|mm|ST|MI)\d{4}-\d{1,2}.*?(_\d{1,2})?"
                                        r"-(?P<position>\d[abcd])(-(m\d+)?)?" + pattern_suffix, re.IGNORECASE)
        acme2_file_pattern = re.compile(r"(JH|SW|JG|JL|SL|TS|PW|mm|ST|MI|SK|MW)\d{4}-\d{1,2}.*?(_\d{1,2})?"
                                        r"-(?P<position>[abc]\d{1,2})(-m\d+)?" + pattern_suffix, re.IGNORECASE)
        emilio_file_pattern = re.compile(r"\d\d[A-Z]\d{2,4}[_A-Z]*-(?P<position>\d{1,2})" + pattern_suffix, re.IGNORECASE)
        defered_filepaths = set()

        latest_measurement_by_day = {}

        changed, removed = find_changed_files(root_dir, diff_file, r".+\.as[wobd]$")
        for data_file in changed:
            try:
                solarsimulator_measurement, sample_name, filename = extract_data_from_file(data_file)
                single_cell_position = None
                layout_name = "juelich standard"
                if len(solarsimulator_measurement.cells) == 1:
                    base_filename = os.path.basename(filename)
                    acme1_file_pattern_match = acme1_file_pattern.match(base_filename)
                    if acme1_file_pattern_match \
                        and solarsimulator_measurement.operator in ["u_dagkaldiran", "j.woerdenweber", "p_woebkenberg",
                                                                    "t.bronger", "j.kroll"]:
                        single_cell_position = acme1_file_pattern_match.group("position").upper()
                        layout_name = "ACME 1"
                    else:
                        acme2_file_pattern_match = acme2_file_pattern.match(base_filename)
                        if acme2_file_pattern_match \
                            and solarsimulator_measurement.operator in ["j.woerdenweber", "p_woebkenberg", "t.bronger"]:
                            single_cell_position = acme2_file_pattern_match.group("position").upper()
                            layout_name = "ACME 2"
                        else:
                            emilio_file_pattern_match = emilio_file_pattern.match(base_filename)
                            if emilio_file_pattern_match and solarsimulator_measurement.operator == "e.marins":
                                single_cell_position = emilio_file_pattern_match.group("position")
                                layout_name = "juelich standard"
                            else:
                                # Match for further cell layouts here
                                pass
                    if single_cell_position:
                        solarsimulator_measurement.cells.values()[0].position = single_cell_position
                sample_id = get_or_create_sample(sample_name, None, solarsimulator_measurement.timestamp,
                                                 solarsimulator_measurement.timestamp_inaccuracy, create=import_legacy_data)
                if not sample_id:
                    raise CrawlerWarning('"{0}" not found in the database; ignored'.format(sample_name))
                solarsimulator_measurement.sample_id = sample_id

                only_single_cell_added = False
                if single_cell_position:
                    cell = solarsimulator_measurement.cells.values()[0]
                    matching_solarsimulator_measurement_id = connection.open(
                        "solarsimulator_measurements/matching/{0}/{1}/{2}/{3}/?filepath={4}".format(*[
                            urllib.quote_plus(unicode(part).encode("utf-8")) for part in [
                                    solarsimulator_measurement.irradiance, sample_id, cell.position,
                                    solarsimulator_measurement.timestamp.date(), filename]]))
                    if matching_solarsimulator_measurement_id:
                        solarsimulator_measurement = SolarsimulatorDarkMeasurement(matching_solarsimulator_measurement_id) \
                            if solarsimulator_measurement.irradiance == "dark" \
                            else SolarsimulatorPhotoMeasurement(matching_solarsimulator_measurement_id)
                        if cell.position in solarsimulator_measurement.cells:
                            solarsimulator_measurement.edit_description = 'Edited "{0}".'.format(cell.data_file)
                            logging.info("Position {position} was editied in solarsimulator measurement #{id}.".format(
                                    position=cell.position, id=matching_solarsimulator_measurement_id))
                        else:
                            solarsimulator_measurement.edit_description = 'Added "{0}".'.format(cell.data_file)
                            only_single_cell_added = True
                            logging.info("Position {position} was added to solarsimulator measurement #{id}.".format(
                                    position=cell.position, id=matching_solarsimulator_measurement_id))
                        solarsimulator_measurement.cells[cell.position] = cell
                    else:
                        logging.info("MAIKE measurement of {sample} was added.".format(sample=sample_name))
                else:
                    try:
                        process_id = connection.open("solarsimulator_measurements/by_filepath?filepath=" +
                                                     urllib.quote_plus(filename.encode("utf-8")))
                    except ChantalError as e:
                        if e.error_code != 2:
                            raise
                        logging.info("MAIKE measurement of {sample} was added.".format(sample=sample_name))
                    else:
                        try:
                            old_measurement = SolarsimulatorPhotoMeasurement(process_id)
                        except ChantalError as error:
                            if error.error_code != 2:
                                raise
                            old_measurement = SolarsimulatorDarkMeasurement(process_id)
                        solarsimulator_measurement.process_id = process_id
                        solarsimulator_measurement.existing = True
                        solarsimulator_measurement.edit_description = "Edited by MAIKE crawler."
                        solarsimulator_measurement.timestamp = old_measurement.timestamp
                        solarsimulator_measurement.timestamp_inaccuracy = old_measurement.timestamp_inaccuracy
                        logging.info("MAIKE measurement of {sample} was changed.".format(sample=sample_name))
                if not solarsimulator_measurement.existing:
                    date = solarsimulator_measurement.timestamp.date()
                    if date in latest_measurement_by_day:
                        if solarsimulator_measurement.timestamp_inaccuracy == 3:
                            solarsimulator_measurement.timestamp = \
                                latest_measurement_by_day[date] + datetime.timedelta(seconds=1)
                        latest_measurement_by_day[date] = max(latest_measurement_by_day[date],
                                                              solarsimulator_measurement.timestamp)
                    else:
                        latest_measurement_by_day[date] = solarsimulator_measurement.timestamp
                solarsimulator_measurement.submit(only_single_cell_added)

                structuring = connection.open("structurings/by_sample/{0}?timestamp={1}".format(
                        urllib.quote_plus(str(sample_id)), urllib.quote_plus(str(solarsimulator_measurement.timestamp))))
                if not structuring:
                    logging.info("create structuring for sample {sample}".format(sample=sample_name))
                    structuring = Structuring()
                    structuring.sample_id = sample_id
                    structuring.process_id = None
                    # FixMe: As long as editing structurings is not possible.
                    structuring.operator = "nobody"
                    structuring.timestamp = solarsimulator_measurement.timestamp - datetime.timedelta(seconds=1)
                    structuring.timestamp_inaccuracy = solarsimulator_measurement.timestamp_inaccuracy
                    structuring.comments = "automaticaly generated"
                    structuring.layout = layout_name
                    logging.debug("set structuring layout to {layout}".format(layout=structuring.layout))
                    structuring.submit()
                # Only to adjust the timestamp of the substrate because the
                # structuring may have been inserted
                assert get_or_create_sample(sample_name, None,
                                            solarsimulator_measurement.timestamp - datetime.timedelta(seconds=2),
                                            solarsimulator_measurement.timestamp_inaccuracy, create=False)
                chantal_remote.connection.open("change_my_samples", {"remove": sample_id})
            except CrawlerWarning as e:
                relative_path = os.path.relpath(data_file, root_dir)
                logging.warning('Warning at "{0}": {1}'.format(relative_path.decode("utf-8"), e))
                defered_filepaths.add(relative_path)
            except Exception as e:
                relative_path = os.path.relpath(data_file, root_dir)
                logging.error('Error at "{0}": {1}'.format(relative_path.decode("utf-8"), e))
                defered_filepaths.add(relative_path)
        defer_files(diff_file, defered_filepaths)
        logout()
