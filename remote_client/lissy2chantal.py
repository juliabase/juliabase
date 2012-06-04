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
import chantal_remote
import os, os.path, re, codecs, datetime, logging, glob, datetime, smtplib, random
from email.MIMEText import MIMEText
import csv, cStringIO

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))


login(credentials["crawlers_login"], credentials["crawlers_password"], testserver=True)


def not_a_number(field):
    if field == "":
        return False
    try:
        float(field)
    except ValueError:
        return True
    else:
        return False


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


def detect_room_temperature(field):
    if field.lower() == "rt":
        return "21"
    else:
        return field


def get_layer_extractor(run, i):
    def layer_extractor(field_name):
        try:
            return run[field_name].split("/")[i]
        except IndexError:
            return run[field_name].split("/")[0]
    return layer_extractor


def get_field_cleaner(layer, remarks):
    def clean_field(fieldname, verbose_fieldname, default=""):
        value = getattr(layer, fieldname)
        if "-" in value and not value.startswith("-"):
            remarks.append("“{0}” contained “{1}”.".format(verbose_fieldname, value))
            value = value.partition("-")[0]
            setattr(layer, fieldname, value)
        if not_a_number(value):
            remarks.append("“{0}” contained “{1}”.".format(verbose_fieldname, value))
            setattr(layer, fieldname, default)
        elif value != "":
            if int(float(value)) == float(value):
                setattr(layer, fieldname, str(int(float(value))))
    return clean_field


already_available_numbers = LargeSputterDeposition.get_already_available_deposition_numbers()


columns = {
    "2001": ("deposition number", "sample", "target", "mode", "base pressure", "generator power",
             "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "steps", "T_heater", "Ts start", "Ts end",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "position3 Rsq",
             "position3 thickness", "position3 deposition rate", "position3 specific resistance",
             "position21 Rsq", "position21 thickness", "position21 deposition rate",
             "position21 specific resistance", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "comments"),
    "2002": ("deposition number", "sample", "cleaning", "target", "mode", "base pressure", "generator power",
             "power density", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "Ts start", "Ts end",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "position3 Rsq",
             "position3 thickness", "position3 deposition rate", "position3 specific resistance", "position3 transparency 800",
             "position3 transparency 1100", "position21 Rsq", "position21 thickness", "position21 deposition rate",
             "position21 specific resistance", "position21 transparency 800", "position21 transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "__", "__1", "Al content", "__2", "__3"),
    "2004": ("deposition number", "date", "sample", "target", "mode", "base pressure", "generator power",
             "power density", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "Ts start", "Ts end",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "position3 Rsq",
             "position3 thickness", "position3 deposition rate", "position3 specific resistance", "position3 transparency 800",
             "position3 transparency 1100", "position21 Rsq", "position21 thickness", "position21 deposition rate",
             "position21 specific resistance", "position21 transparency 800", "position21 transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "etching rate 2", "__", "Al content", "__2"),
    "2006": ("deposition number", "date", "sample", "owner", "target", "mode", "base pressure", "generator power",
             "power density", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "TsMC", "TsLL",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "position3 Rsq",
             "position3 thickness", "position3 deposition rate", "position3 specific resistance", "position3 transparency 800",
             "position3 transparency 1100", "position21 Rsq", "position21 thickness", "position21 deposition rate",
             "position21 specific resistance", "position21 transparency 800", "position21 transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "etching rate 2", "__", "Al content", "__2",
             "haze", "cell 1 eta", "cell 1 FF", "cell 1 Voc", "cell 1 Jsc", "__3", "cell 2 eta", "cell 2 FF",
             "cell 2 Voc", "cell 2 Jsc", "__4", "cell 3 eta", "cell 3 FF", "cell 3 Voc", "cell 3 Jsc", "__5",
             "cell 4 eta", "cell 4 FF", "cell 4 Voc", "cell 4 Jsc", "__6", "__7"),
    "2008": ("deposition number", "date", "sample", "owner", "target", "mode", "base pressure", "generator power",
             "power density", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "TsMC", "TsLL", "RDM",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "position3 Rsq",
             "position3 thickness", "position3 deposition rate", "position3 specific resistance", "position3 transparency 800",
             "position3 transparency 1100", "position21 Rsq", "position21 thickness", "position21 deposition rate",
             "position21 specific resistance", "position21 transparency 800", "position21 transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "etching rate 2", "__", "Al content", "__2",
             "haze", "cell 1 eta", "cell 1 FF", "cell 1 Voc", "cell 1 Jsc", "__3", "cell 2 eta", "cell 2 FF",
             "cell 2 Voc", "cell 2 Jsc", "__4", "cell 3 eta", "cell 3 FF", "cell 3 Voc", "cell 3 Jsc", "__5",
             "cell 4 eta", "cell 4 FF", "cell 4 Voc", "cell 4 Jsc", "__6", "__7"),
    "2009": ("deposition number", "date", "sample", "owner", "target", "mode", "base pressure", "generator power",
             "total power target", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "TsMC", "TsLL", "RDM",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "position3 Rsq",
             "position3 thickness", "position3 deposition rate", "position3 specific resistance", "position3 transparency 800",
             "position3 transparency 1100", "position21 Rsq", "position21 thickness", "position21 deposition rate",
             "position21 specific resistance", "position21 transparency 800", "position21 transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "etching rate 2", "__", "Al content", "__2",
             "haze", "cell 1 eta", "cell 1 FF", "cell 1 Voc", "cell 1 Jsc", "__3", "cell 2 eta", "cell 2 FF",
             "cell 2 Voc", "cell 2 Jsc", "__4", "cell 3 eta", "cell 3 FF", "cell 3 Voc", "cell 3 Jsc", "__5",
             "cell 4 eta", "cell 4 FF", "cell 4 Voc", "cell 4 Jsc", "__6", "__7"),
    "2010": ("deposition number", "date", "sample", "owner", "target", "mode", "base pressure", "generator power",
             "total power target", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "TsMC", "TsLL", "RDM",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "smooth Rsq",
             "smooth thickness", "smooth deposition rate", "smooth specific resistance", "smooth transparency 800",
             "smooth transparency 1100", "etched Rsq", "etched thickness", "etched etching rate",
             "etched specific resistance", "etched transparency 800", "etched transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "etching rate 2", "__", "Al content", "__2",
             "haze", "cell 1 eta", "cell 1 FF", "cell 1 Voc", "cell 1 Jsc", "__3", "cell 2 eta", "cell 2 FF",
             "cell 2 Voc", "cell 2 Jsc", "__4", "cell 3 eta", "cell 3 FF", "cell 3 Voc", "cell 3 Jsc", "__5",
             "cell 4 eta", "cell 4 FF", "cell 4 Voc", "cell 4 Jsc", "__6", "__7"),
    "2011": ("deposition number", "date", "sample", "owner", "target", "mode", "base pressure", "generator power",
             "total power target", "generator voltage 1", "generator voltage 2", "generator current 1",
             "generator current 2", "feed rate", "static time", "steps", "T_heater", "TsMC", "TsLL", "RDM",
             "throttle", "work pressure", "Ar1", "Ar2", "O2", "O2 2", "O2 in Ar", "PEM 1", "PEM 2", "smooth Rsq",
             "smooth thickness", "smooth deposition rate", "smooth specific resistance", "smooth transparency 800",
             "smooth transparency 1100", "etched Rsq", "etched thickness", "etched etching rate",
             "etched specific resistance", "etched transparency 800", "etched transparency 1100", "position45 Rsq",
             "position45 thickness", "position45 deposition rate", "position45 specific resistance",
             "position45 transparency 800", "position45 transparency 1100", "film thickness", "resistivity",
             "carrier concentration", "carrier mobility", "etching rate", "etching rate 2", "__", "Al content", "__2",
             "haze", "cell 1 eta", "cell 1 FF", "cell 1 Voc", "cell 1 Jsc", "__3", "cell 2 eta", "cell 2 FF",
             "cell 2 Voc", "cell 2 Jsc", "__4", "cell 3 eta", "cell 3 FF", "cell 3 Voc", "cell 3 Jsc", "__5",
             "cell 4 eta", "cell 4 FF", "cell 4 Voc", "cell 4 Jsc", "__6", "__7"),
    }
columns["2007"] = columns["2008"]
columns["2005"] = columns["2006"]
columns["2003"] = columns["2004"]

deposition_number_pattern = re.compile("\d\dV-(?P<index>\d{3,4})([ab]|-[12])?$")
time_in_minutes = re.compile("(?P<minutes>\d+)\s*min", re.IGNORECASE)
time_in_hours = re.compile("(?P<hours>\d+)\s*h", re.IGNORECASE)
try:
    for year in [str(i) for i in range(2011, 2000, -1)]:
        reader = UnicodeReader(open("/tmp/lissy_protokolle/lissy_{0}.csv".format(year), "rb"), delimiter=",")
        deposition_numbers = set()
        runs = []
        for line in reader:
            run = dict((label, cell.strip()) for label, cell in zip(columns[year], line))
            if run["deposition number"] == "09V-284":
                if run["date"] == "07.04.2009":
                    run["deposition number"] += "a"
                else:
                    run["deposition number"] += "b"
            elif run["deposition number"] == "04V-225":
                if run["date"] == "27.05.2004":
                    run["deposition number"] += "a"
                else:
                    run["deposition number"] += "b"
            elif run["deposition number"] == "04V-375" and run["O2 in Ar"] == "152":
                # double entry
                continue
            elif run["deposition number"] in ["09V-407", "09V-918", "09V-1017"]:
                run["mode"] = "R-MF"
            elif run["deposition number"] in ["08V-819", "08V-820"]:
                run["date"] = "18.11.2008"
            # elif run["deposition number"] in ["08V-679", "08V-708", "05V-047", "05V-131", "04V-430", "04V-558", "03V-153",
            #                                   "03V-176", "03V-250", "03V-257"]:
            #     run["generator current 1"] = run["generator current 2"] = ""
            elif run["deposition number"] == "08V-895":
                run["date"] = "17.12.2008"
            elif run["deposition number"] == "08V-906":
                run["date"] = "19.12.2008"
            elif run["deposition number"] == "08V-907":
                run["date"] = "22.12.2008"
            elif run["deposition number"] == "06V-637":
                run["date"] = "12.10.2006"
            elif run["deposition number"] == "06V-693":
                run["date"] = "14.11.2006"
            elif run["deposition number"] in ["05V-763", "05V-765"]:
                run["date"] = "09.12.2005"
            elif run["deposition number"] in ["05V-771", "05V-772", "05V-773"]:
                run["date"] = "15.12.2005"
            elif run["deposition number"] == "05V-781":
                run["date"] = "22.12.2005"
            elif run["deposition number"].startswith("02V-311"):
                run["deposition number"] = "02V-311"
            elif run["deposition number"].startswith("02V-103"):
                run["deposition number"] = "02V-103"
            if "/" in run["deposition number"]:
                run["deposition number"] = run["deposition number"].partition("/")[0]
            if run["mode"] == "R/MF":
                run["mode"] = "R-MF"
            run.setdefault("RDM", "")
            run.setdefault("owner", "")
            try:
                index = int(deposition_number_pattern.match(run["deposition number"]).group("index"))
            except AttributeError:
                index = -1
            run["date"] = run.get("date", "02.01." + year)
            prefix = year[2:] + "V-"
            if run["deposition number"] and run["deposition number"] not in already_available_numbers and \
                    run["deposition number"].startswith(prefix) and run["date"] \
                    and run["generator power"] not in ["no depo", "keine Depo"] and run["mode"] and \
                    not run["mode"] == "nicht gelaufen" \
                    and not run["target"] == "optical measurement" and index > -1:
                if run["deposition number"] in deposition_numbers:
                    # 2002 gab es einige doppelte
                    continue
                deposition_numbers.add(run["deposition number"])
                if run["date"].endswith("1900") or run["date"].endswith("1899") or run["date"] == "?????":
                    run["date"] = last_date
                else:
                    last_date = run["date"]
                if run["date"] == "neues Target":
                    run["date"] = "09.05.2011"
                run["date"] = datetime.datetime.strptime(run["date"], "%d.%m.%Y")
                run["date"] = run["date"].replace(hour=9)
                runs.append(run)
        runs.sort(key=lambda run: (run["date"], run["deposition number"]))

        cg_pattern = re.compile(r"(\d\*)?CG\+?|corning(glas)?( [0-9*m]+)?", re.IGNORECASE)
        al_pattern = re.compile(r"Al.folie|Alufolie", re.IGNORECASE)
        n_number_pattern = re.compile(r"\d\dN-?\d{3}", re.IGNORECASE)
        wafer_pattern = re.compile(r"wafer|c-si", re.IGNORECASE)
        quarz_pattern = re.compile(r"quart?z(glas)?", re.IGNORECASE)
        asahi_u_pattern = re.compile(r"asahi.u", re.IGNORECASE)
        current_day = None
        last_timestamp = None
        for run in runs:
            comments = "This run was automatically imported.  \nOriginal “substrate”: {0}  \n".format(run["sample"])
            if run["owner"]:
                comments += "Original “owner”: {0}  \n".format(run["owner"])

            if not run["target"] or run["target"] in ["annealing", "Tempern"]:
                continue
            if run["target"] == "soft ZAO-ZAO":
                run["target"] = "soft ZAO/ZAO"
            elif run["target"] == "ZnOAl2O3 1%/0,5%":
                run["target"] = "ZnOAl2O3 1%/ZnOAl2O3 0,5%"
            elif run["target"] in ["nH ZnOAl2O3 1%", "sH ZnOAl2O3 1%"]:
                run["target"] = "ZnOAl2O3 1%"
            elif run["target"] == "0,2%ZnAl":
                run["target"] = "ZnAl 0.2%"
            elif run["target"] == "1%ZnAl":
                run["target"] = "ZnAl 1%"
            elif run["target"] == "ZAO/Ag/":
                run["target"] = "ZAO/Ag/ZAO"
                comments += "The last layer may be bogus.  \n"

            if run["mode"] == "rfDC":
                run["mode"] = "rf/DC"
            run["mode"] = run["mode"].replace("+", "/")

            timestamp = run["date"]
            if timestamp.toordinal() != current_day:
                current_day = timestamp.toordinal()
                current_day_index = 1
            if timestamp == last_timestamp:
                run["date"] += datetime.timedelta(seconds=current_day_index)
                current_day_index += 1
            last_timestamp = timestamp
            run["timestamp inaccuracy"] = 3

            substrate_raw = run["sample"].strip()
            sample_name = run["deposition number"]
            if cg_pattern.match(substrate_raw):
                substrate = "corning"
            elif al_pattern.match(substrate_raw):
                substrate = "aluminium"
            elif n_number_pattern.match(substrate_raw):
                substrate = "corning"
            elif wafer_pattern.match(substrate_raw):
                substrate = "wafer"
            elif quarz_pattern.match(substrate_raw):
                substrate = "quarz"
            elif asahi_u_pattern.match(substrate_raw):
                substrate = "asahi"
            else:
                substrate = None
                sample_name = "unknown-" + run["deposition number"]
            sample_id = get_or_create_sample(sample_name, substrate, run["date"], run["timestamp inaccuracy"])

            deposition = LargeSputterDeposition()
            deposition.sample_ids = [sample_id]
            deposition.number = run["deposition number"]
            deposition.operator = "nobody"
            deposition.timestamp = run["date"]
            deposition.timestamp_inaccuracy = run["timestamp inaccuracy"]
            deposition.comments = comments
            deposition.loadlock = "??"

            number_of_layers = max(len(run["target"].split("/")), len(run["generator power"].split("/")))
            for i in range(number_of_layers):
                get_layer_data = get_layer_extractor(run, i)
                layer = LargeSputterLayer(deposition)
                remarks = []
                clean_field = get_field_cleaner(layer, remarks)
                layer.target = get_layer_data("target").replace(",", ".")
                if layer.target in ["nH ZnOAl2O3 0.5%", "sH ZnOAl2O3 0.5%", "hp ZnOAl2O3 0.5%", "0.5%ZnOAl2O3"]:
                    layer.target = "ZnOAl2O3 0.5%"
                elif layer.target in ["soft ZAO", "soft"]:
                    layer.target = "ZnOAl2O3 1%"
                    remarks.append("target {0} was “soft”".format(i + 1))
                elif layer.target in ["ZAO", "ZA", "nH ZAO", "1%ZnOAl2O3"]:
                    layer.target = "ZnOAl2O3 1%"
                elif layer.target == "ZnOAl2O3":
                    layer.target = "ZnOAl2O3 2%"
                elif layer.target == "0.5%ZnAl":
                    layer.target = "ZnAl 0.5%"
                elif layer.target == "2%ZnOAl2O3":
                    layer.target = "ZnOAl2O3 2%"
                elif layer.target == "2%ZnAl":
                    layer.target = "ZnAl 2%"
                elif layer.target == "ZnAl":
                    layer.target = "ZnAl 2%"
                elif layer.target.lower().startswith("ion"):
                    layer.target = "Ion"
                layer.mode = get_layer_data("mode").strip()
                if layer.mode.lower() == "dc":
                    layer.mode = "DC"
                elif layer.mode.lower() in ["rf", "tf"]:
                    layer.mode = "rf"
                elif layer.mode.lower() == "mf":
                    layer.mode = "MF"
                elif layer.mode == "p":
                    layer.mode = "pulse"
                layer.rpm = run["RDM"]
                if layer.rpm in ["10?", "~10"]:
                    remarks.append("RPM number is uncertain")
                    layer.rpm = "10"
                if layer.rpm:
                    layer.rpm = int(float(layer.rpm.replace(",", ".")))
                layer.temperature_ll = detect_room_temperature(run.get("TsLL", ""))
                clean_field("temperature_ll", "T_LL")
                layer.temperature_pc_2 = detect_room_temperature(get_layer_data("T_heater"))
                clean_field("temperature_pc_2", "T_PC 2")
                layer.temperature_smc_2 = detect_room_temperature(run.get("TsMC", ""))
                clean_field("temperature_smc_2", "TsMC 2")
                layer.operating_pressure = get_layer_data("work pressure").replace(",", ".") or "-1"
                clean_field("operating_pressure", "operating pressure", "-1")
                layer.base_pressure = run["base pressure"].replace(",", ".")
                if layer.base_pressure in ["<1", "<2", "<7"]:
                    remarks.append("“base pressure” was “{0}”".format(layer.base_pressure))
                    layer.base_pressure = ""
                clean_field("base_pressure", "base pressure")
                def clean_tilde(fieldname):
                    if run[fieldname].startswith("~"):
                        remarks.append("“{0}” was {1}".format(fieldname, run[fieldname]))
                        run[fieldname] = run[fieldname][1:]
                if run.get("total power target") is not None:
                    clean_tilde("total power target")
                    layer.accumulated_power = get_layer_data("total power target").replace(",", ".")
                    clean_field("accumulated_power", "accumulated power")
                clean_tilde("throttle")
                layer.throttle = get_layer_data("throttle").replace(",", ".")
                clean_field("throttle", "throttle", "-1")
                layer.gen_power = get_layer_data("generator power").replace(",", ".")
                clean_field("gen_power", "generator power")
                clean_tilde("generator voltage 1")
                clean_tilde("generator voltage 2")
                clean_tilde("generator current 1")
                clean_tilde("generator current 2")
                if run["generator voltage 1"]:
                    layer.voltage_1 = get_layer_data("generator voltage 1").replace(",", ".")
                    clean_field("voltage_1", "voltage 1")
                layer.voltage_2 = get_layer_data("generator voltage 2").replace(",", ".")
                clean_field("voltage_2", "voltage 2")
                layer.voltage_1 = layer.voltage_1 and int(float(layer.voltage_1))
                layer.voltage_2 = layer.voltage_2 and int(float(layer.voltage_2))
                if layer.mode == "rf":
                    cl = get_layer_data("generator current 1").replace(",", ".")
                    if cl and "." not in cl:
                        layer.cl = layer.cl
                        layer.ct = get_layer_data("generator current 1").replace(",", ".")
                        if layer.ct:
                            assert float(layer.ct) == int(float(layer.ct))
                            layer.ct = int(float(layer.ct))
                else:
                    layer.current_1 = run["generator current 1"].replace(",", ".")
                    layer.current_2 = run["generator current 2"].replace(",", ".")
                    clean_field("current_1", "current 1")
                    clean_field("current_2", "current 2")
                    if layer.current_1.endswith("mA"):
                        layer.current_1 = float(layer.current_1[:-2]) / 1000.0
                    if layer.current_1 and float(layer.current_1) > 100 or layer.current_2 and float(layer.current_2) > 100:
                        layer.current_1 = layer.current_2 = ""
                layer.feed_rate = get_layer_data("feed rate")
                if "+" in layer.feed_rate:
                    remarks.append("“feed rate” was " + layer.feed_rate)
                    layer.feed_rate = layer.feed_rate.partition("+")[0]
                layer.feed_rate = layer.feed_rate.replace(",", ".")
                clean_field("feed_rate", "feed rate")
                steps = get_layer_data("steps")
                if steps == "?":
                    remarks.append("Überläufe sind unbekannt.")
                    steps = ""
                if "+" in steps:
                    layer.steps = str(eval(steps))
                    remarks.append("“steps” was " + steps)
                else:
                    layer.steps = steps
                clean_field("steps", "steps")
                layer.static_time = run.get("static time", "")
                match = time_in_minutes.match(layer.static_time.strip())
                if match:
                    layer.static_time = 60 * float(match.group("minutes"))
                else:
                    match = time_in_hours.match(layer.static_time.strip())
                    if match:
                        layer.static_time = 3600 * float(match.group("hours"))
                    else:
                        if layer.static_time == "7kWh":
                            layer.static_time = ""
                        else:
                            clean_field("static_time", "static time")
                            if layer.static_time != "":
                                layer.static_time = float(layer.static_time)
                if isinstance(layer.static_time, float):
                    layer.static_time = "{0:.2g}".format(float(layer.static_time) / 60)
                layer.ar_1 = get_layer_data("Ar1").replace("-", "").replace(",", ".")
                layer.ar_1 = get_layer_data("Ar2").replace("-", "").replace(",", ".")
                clean_field("ar_1", "Ar 1")
                layer.o2_1 = get_layer_data("O2").replace(",", ".")
                layer.o2_2 = get_layer_data("O2 2").replace(",", ".")
                clean_field("o2_1", "O₂ 1")
                clean_field("o2_2", "O₂ 2")
                layer.ar_o2 = run["O2 in Ar"].replace(",", ".")
                clean_field("ar_o2", "Ar/O₂")
                if run["PEM 1"]:
                    layer.pem_1 = get_layer_data("PEM 1").replace(",", ".")
                    clean_field("pem_1", "PEM 1")
                    if layer.pem_1:
                        layer.pem_1 = int(float(layer.pem_1))
                if run["PEM 2"]:
                    layer.pem_2 = get_layer_data("PEM 2").replace(",", ".")
                    clean_field("pem_2", "PEM 2")
                    if layer.pem_2:
                        layer.pem_2 = int(float(layer.pem_2))
                layer.layer_description = "  \n".join(remarks)
            deposition.submit()
            if len(deposition.layers) == 1:
                r_square = (run.get("smooth Rsq") or run.get("position3 Rsq") or "").replace(",", ".")
                thickness = run.get("smooth thickness") or run.get("position3 thickness") or ""
                if r_square != "" or thickness != "":
                    sputter_characterization = SputterCharacterization()
                    sputter_characterization.sample_id = sample_id
                    sputter_characterization.operator = "nobody"
                    sputter_characterization.timestamp = run["date"] + datetime.timedelta(seconds=1)
                    sputter_characterization.timestamp_inaccuracy = run["timestamp inaccuracy"]
                    sputter_characterization.comments = "This characterisation was automatically imported."
                    sputter_characterization.large_sputter_deposition = deposition.number
                    if not_a_number(r_square):
                        sputter_characterization.comments += "  \nR_□ contained “{0}”.".format(r_square)
                    else:
                        sputter_characterization.r_square = r_square
                    if not_a_number(thickness):
                        sputter_characterization.comments += "  \nthickness contained “{0}”.".format(thickness)
                    else:
                        sputter_characterization.thickness = thickness
                    sputter_characterization.submit()
            chantal_remote.connection.open("change_my_samples", {"remove": sample_id})
except Exception as e:
    raise
    s = smtplib.SMTP_SSL("relay-auth.rwth-aachen.de")
    s.login("bronger+physik.rwth-aachen.de", "Saiph1_")
    message = MIMEText(("Fehler beim LISSY-Import").encode("iso-8859-1"), _charset = "iso-8859-1")
    message["Subject"] = "LISSY-Import-Fehler " + str(random.random())
    message["From"] = "bronger@physik.rwth-aachen.de"
    message["To"] = "bronger.randy@googlemail.com"
    s.sendmail("bronger@physik.rwth-aachen.de", ["bronger.randy@googlemail.com"], message.as_string())
    raise


logout()
