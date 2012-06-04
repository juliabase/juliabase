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

from __future__ import absolute_import, unicode_literals
from chantal_remote import FiveChamberDeposition, FiveChamberLayer, \
    get_or_create_sample, login, logout, ChantalError, connection, setup_logging
from shared_utils import sanitize_for_markdown
import ConfigParser
import codecs
import datetime
import logging
import os.path
import re

setup_logging(True)
my_logger = logging.FileHandler("/home/chantal/crawler_data/five_chamber.log", "a")
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
my_logger.setFormatter(formatter)
my_logger.setLevel(logging.INFO)
logging.getLogger("").addHandler(my_logger)

logging.info("started crawling")

credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("/var/www/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

def isFloat(s):
    try:
        float(s)
    except (ValueError, TypeError):
        return False
    else:
        return True


digit_search_pattern = re.compile(r"(?P<digit>\d+)")
sample_name_pattern = re.compile(r"\"(?P<year>\d\d)(?P<letter>[Ss])-?(?P<number>\d{3})(?P<suffix>[-A-Za-z_/#()][-A-Za-z_/0-9#()]*)?\",*")
class FiveChamberData():
    def __init__(self):
        self.sample_name = self.date = self.chamber = self.sih4 = self.h2 = self.tmb = \
            self.ch4 = self.co2 = self.ph3 = self.power = self.pressure = self.temperature = \
            self.fHF = self.time = self.dc_bias = self.substrate = self.elektr_abst = self.comments = None

    def get_sample_name(self):
        return self.sample_name[1:8]

    def get_date(self):
        if self.date and self.date[1:-1] == "nicht gemacht":
            self.date = None
        if self.date:
            day, month, year = self.date.split('/')
            timestamp_inaccuracy = 3
        elif self.sample_name:
            year = self.sample_name.strip('"')[:2]
            month = 1
            day = 1
            timestamp_inaccuracy = 5
        if len(year) == 2:
            year = "20{0}".format(year)
        return datetime.datetime(int(year), int(month), int(day), 8, 0, 0), timestamp_inaccuracy

    def get_chamber(self):
        chamber = self.chamber.strip('"')
        if chamber and chamber in ["i1", "i2", "i3", "p", "n"]:
            return chamber
        elif "E" in chamber:
            return "i3"

    def get_sih4(self):
        if self.sih4:
            sih4 = unicode(self.sih4).encode("utf-8").strip('"')
            if sih4.isdigit() or isFloat(sih4):
                return round(float(sih4), 3), "sih4"
            elif "NF3" in sih4:
                return digit_search_pattern.search(sih4.replace("NF3", "nf")).group("digit"), "nf3"
            else:
                return sih4, "comments"

    def get_h2(self):
        if self.h2:
            h2 = str(self.h2).strip('"')
            if h2.isdigit() or isFloat(h2):
                return round(float(self.h2), 3), "h2"
            else:
                return h2, "comments"

    def get_tmb(self):
        if self.tmb:
            tmb = str(self.tmb).strip('"')
            if tmb.isdigit() or isFloat(tmb):
                return round(float(tmb), 3), "tmb"
            elif "NF3" in tmb:
                return digit_search_pattern.search(tmb.replace("NF3", "nf")).group("digit") or '40', "nf3"
            else:
                return tmb, "comments" #nf3 = 0

    def get_ch4(self):
        if self.ch4:
            ch4 = str(self.ch4).strip('"')
            if ch4.isdigit() or isFloat(ch4):
                return ch4, "ch4"
            else:
                return ch4, "impurity"

    def get_co2(self):
        return self.co2

    def get_ph3(self):
        return self.ph3

    def get_power(self):
        if self.power:
            power = str(self.power).strip('"')
            if power.isdigit() or isFloat(power):
                return power, "power"
            else:
                return power, "comments"

    def get_pressure(self):
        if self.pressure:
            pressure = str(self.pressure).strip('"')
            if pressure.isdigit() or isFloat(pressure):
                return pressure, "pressure"
            else:
                return pressure, "comments"

    def get_temperature(self):
        if self.temperature:
            if "RT" in self.temperature:
                return 20
            elif "/" in self.temperature:
                return self.temperature.strip('"').split("/")[0]
        else:
            return self.temperature

    def get_frequency(self):
        if self.fHF:
            return self.fHF.split('"')

    def get_time(self):
        if self.time:
            time = str(self.time).strip('"')
            if time.isdigit():
                return time, "time"
            else:
                return "{0} seconds".format(time), "comments"

    def get_dc(self):
        if self.dc_bias:
            dc = str(self.dc_bias).strip('"')
            if dc.isdigit():
                return dc, "dc_bias"
            else:
                return dc, "comments"

    def get_substrate(self):
        return self.substrate.strip('"')

    def get_dist(self):
        return self.elektr_abst

    def get_comments(self):
        if self.comments:
            return self.comments.encode("utf-8")[1:-1]
        else:
            return ""

def fill_deposition_layer(layer, data, comments):
    if data.get_pressure() and data.get_pressure()[1] == "pressure":
        layer.pressure = data.get_pressure()[0]
    elif data.get_pressure() and data.get_pressure()[1] == "comments":
        comments += "  \npressure changed during deposition: {0}".format(data.get_pressure()[0])
        layer.pressure = 0

    if data.get_time() and data.get_time()[1] == "time":
        layer.time = data.get_time()[0]
    elif data.get_time() and data.get_time()[1] == "comments":
        comments += "  \ndeposition time: {0}".format(data.get_time()[0])
        layer.time = 0

    layer.electrode_distance = data.get_dist()
    layer.temperature_1 = data.get_temperature()
    layer.hf_frequency = data.get_frequency()

    if data.get_power() and data.get_power()[1] == "power":
        layer.power = data.get_power()[0]
    elif data.get_power() and data.get_power()[1] == "comments":
        comments += "  \npower changed during deposition: {0}".format(data.get_power()[0])
        layer.power = 0

    if data.get_sih4() and data.get_sih4()[1] == "sih4":
        layer.sih4 = data.get_sih4()[0]
    elif data.get_sih4() and data.get_sih4()[1] == "comments":
        comments += "  \nsilane flow rate changed during deposition: " + data.get_sih4()[0].decode("utf-8")
        layer.sih4 = 0

    if data.get_h2() and data.get_h2()[1] == "h2":
        layer.h2 = data.get_h2()[0]
    elif data.get_h2() and data.get_h2()[1] == "comments":
        comments += "\nH₂: " + data.get_h2()[0]
        layer.h2 = 0

    if data.get_ch4() and data.get_ch4()[1] == "ch4":
        layer.ch4 = data.get_ch4()[0]
    elif data.get_ch4() and data.get_ch4()[1] == "impurity":
        gas = data.get_ch4()[0]
        if "O" in gas:
            layer.impurity = "O2"
        elif "N" in gas:
            layer.impurity = "N2"
        elif "air" in gas.lower():
            layer.impurity = "Air"

    layer.co2 = data.get_co2()
    layer.date = data.get_date()[0].date()

    if data.get_dc() and data.get_dc()[1] == "dc_bias":
        layer.dc_bias = data.get_dc()[0]
    elif data.get_dc() and data.get_dc()[1] == "comments":
        comments += "  \ndc bias: {0}".format(data.get_dc()[0])
        layer.dc_bias = 0

    if data.get_tmb() and data.get_tmb()[1] == "tmb":
        layer.tmb = data.get_tmb()[0]

    if data.get_ph3():
        layer.ph3 = data.get_ph3()

    if "Raman" in comments:
        layer.in_situ_measurement = "Raman"
    elif "OES" in comments:
        layer.in_situ_measurement = "OES"
    elif "FTIR" in comments:
        layer.in_situ_measurement = "FTIR"

    data.pressure = None
    data.electrode_distance = None
    data.temperature = None
    data.fHF = None
    data.power = None
    data.sih4 = None
    data.h2 = None
    data.tmb = None
    data.ch4 = None
    data.co2 = None
    data.ph3 = None
    data.dc_bias = None
    data.impurity = None
    data.time = None

login(credentials["crawlers_login"], credentials["crawlers_password"])

lines = codecs.open("PECVDData 5K.csv", "r", "UTF-8").readlines()[2:]
five_chamber_depo = FiveChamberDeposition()

for line_counter, line in enumerate(lines):
    if not sample_name_pattern.match(line):
        logging.info("skipped line #{0}".format(line_counter+3))
        continue

    five_chamber_data = FiveChamberData()
    five_chamber_data.sample_name, five_chamber_data.date, _, five_chamber_data.chamber, \
        five_chamber_data.sih4, five_chamber_data.h2, _, five_chamber_data.tmb, five_chamber_data.ch4, \
        five_chamber_data.co2, five_chamber_data.ph3, five_chamber_data.power, five_chamber_data.pressure, \
        five_chamber_data.temperature, five_chamber_data.fHF, five_chamber_data.time, five_chamber_data.dc_bias, \
        _,_,_,five_chamber_data.substrate,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_, five_chamber_data.elektr_abst, \
        five_chamber_data.comments = line.strip().split("$")[:41]

    timestamp, timestamp_inaccuracy = five_chamber_data.get_date()
    add_zno_warning = True if "ZnO" in five_chamber_data.get_substrate() else False
    sample_id = get_or_create_sample(five_chamber_data.get_sample_name(), five_chamber_data.get_substrate(), timestamp,
                         timestamp_inaccuracy, add_zno_warning, create=True)
    if sample_id:
        logging.info("created sample {0}".format(five_chamber_data.get_sample_name()))

    five_chamber_depo.sample_ids = [sample_id]
    if not five_chamber_depo.timestamp:
        five_chamber_depo.timestamp = timestamp
    five_chamber_depo.timestamp_inaccuracy = timestamp_inaccuracy
    five_chamber_depo.number = five_chamber_data.get_sample_name()[:7]
    comments = five_chamber_depo.comments

    five_chamber_p_layer = None
    five_chamber_i_layer = None
    five_chamber_n_layer = None

    if five_chamber_data.get_tmb() and \
       (five_chamber_data.get_tmb()[1] == "tmb" and not five_chamber_data.get_chamber() == "n"):
        logging.info("added p layer to {0}".format(five_chamber_data.get_sample_name()))
        five_chamber_p_layer = FiveChamberLayer(five_chamber_depo)
        five_chamber_p_layer.layer_type = "p"
        five_chamber_p_layer.tmb = five_chamber_data.get_tmb()[0]
        five_chamber_p_layer.chamber = "p"
        five_chamber_data.tmb = None

    if five_chamber_data.get_chamber() not in ["p", "n"]:
        logging.info("added i layer to {0}".format(five_chamber_data.get_sample_name()))
        five_chamber_i_layer = FiveChamberLayer(five_chamber_depo)
        five_chamber_i_layer.layer_type = "i"
        five_chamber_i_layer.chamber = five_chamber_data.get_chamber() or "i1"

    if five_chamber_data.get_ph3() and not five_chamber_data.get_chamber() == "p":
        logging.info("added n layer to {0}".format(five_chamber_data.get_sample_name()))
        five_chamber_n_layer = FiveChamberLayer(five_chamber_depo)
        five_chamber_n_layer.layer_type = "n"
        five_chamber_n_layer.ph3 = five_chamber_data.get_ph3()
        five_chamber_n_layer.chamber = "n"
        five_chamber_data.ph3 = None

    if five_chamber_i_layer == five_chamber_p_layer == five_chamber_n_layer == None:
        continue

    comments += "  \n" + five_chamber_data.get_comments().decode("utf-8")

    if five_chamber_i_layer:
        fill_deposition_layer(five_chamber_i_layer, five_chamber_data, comments)

    if five_chamber_p_layer:
        fill_deposition_layer(five_chamber_p_layer, five_chamber_data, comments)

    if five_chamber_n_layer:
        fill_deposition_layer(five_chamber_n_layer, five_chamber_data, comments)

    five_chamber_depo.comments = sanitize_for_markdown(comments.strip())

    if not lines[line_counter+1].strip().split(",")[0][1:8] == five_chamber_data.get_sample_name():
        try:
            five_chamber_depo.submit()
        except ChantalError as e:
            logging.error("{0}".format(e))
        else:
            logging.info("submited five chamber deposition")
            connection.open("change_my_samples", {"remove": sample_id})
        five_chamber_depo = FiveChamberDeposition()

logout()
