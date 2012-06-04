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
from chantal_remote import LADADeposition, LADALayer, get_or_create_sample, \
    login, logout, ChantalError, setup_logging, connection, comma_separated_ids
from shared_utils import sanitize_for_markdown
import ConfigParser
import codecs
import datetime
import decimal
import logging
import os.path
import re

setup_logging(True)

logging.info("Started legacy import")
my_logger = logging.FileHandler("/home/chantal/crawler_data/lada.log", "a")
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S")
my_logger.setFormatter(formatter)
my_logger.setLevel(logging.INFO)
logging.getLogger("").addHandler(my_logger)

credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("/var/www/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

date_pattern = re.compile(r"#?(?P<day>\d{1,2}).(?P<month>\d{1,2}).(?P<year>\d{2,4})")
def parse_date(datestring):
    match = date_pattern.match(datestring)
    year = int(match.group("year"))
    if year < 100:
        year = 1900 + year if year > 40 else 2000 + year
    return datetime.datetime(year, int(match.group("month")), int(match.group("day")), 8, 0, 0)

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

operator_map = {"AF": "a.flikweert",
                "JW": "j.woerdenweber",
                "TM": "t.merdzhanova",
                "TZ": "t.zimmermann",
                "DW": "d.weigand",
                "KD": "k.ding",
                "BG": "b.grootoonk"}

layer_number_pattern = re.compile(r"(?P<year>\d{2})[dD](?P<number>\d{3,4})")
gradient_pattern = re.compile("(?P<start>\d+\.?\d*)-?(?P<end>\d+\.?\d*)?")
two_value_pattern = re.compile("(?P<first>(\d+\.\d+|\d+))\s*/?\s*(?P<second>(\d+\.\d+)|\d+)?")
class LADAData:

    def __init__(self):
        self.layer_number = self.date = self.operator = \
        self.layer_type = self.chamber = self.h2 = \
        self.sih4 = self.tmb = self.ch4 = self.co2 = \
        self.ph3 = self.additional_gas = self.additional_gas_flow = \
        self.time = self.pressure = self.power = \
        self.hf_frequency = self.electrodes_distance = self.v_lq = \
        self.pendulum_lq = self.temperature_substrate = \
        self.temperature_heater = self.temperature_heater_depo = \
        self.substrate_size = self.glasses = self.power_reflected = \
        self.cl = self.ct = self.u_dc = self.base_pressure = \
        self.comments = self.substrate = self.suffixes = None

    def get_date(self):
        return self.get_datetime().date() if self.date else None

    def get_datetime(self):
        return parse_date(self.date.strip('"')) if self.date else None

    def get_layer_number(self):
        return int(layer_number_pattern.match(self.layer_number.strip('"')).group("number")) \
            if self.layer_number else None

    def get_deposition_number(self):
        return unicode(self.layer_number.strip('"').upper().replace("D", "D-")) \
            if self.layer_number else None

    def get_operator(self):
        return operator_map[re.search("[A-Z]{2}", self.operator).group(0)] if self.operator.strip('"') else None

    def get_layer_type(self):
        return unicode(self.layer_type.strip('"') or "?")

    def get_chamber(self):
        return int(self.chamber or 1)

    def get_vlq(self):
        return decimal.Decimal(self.v_lq) if self.v_lq else None

    def get_pendulum_lq(self):
        return int(self.pendulum_lq) if self.pendulum_lq else None

    def get_h2_start(self):
        if self.h2:
            h2 = self.h2.strip('"')
            return decimal.Decimal(gradient_pattern.match(h2).group("start"))

    def get_h2_end(self):
        if self.h2:
            h2 = self.h2.strip('"')
            if gradient_pattern.match(h2).group("end"):
                return decimal.Decimal(gradient_pattern.match(h2).group("end"))

    def get_sih4_start(self):
        if self.sih4:
            sih4 = self.sih4.strip('"')
            return decimal.Decimal(gradient_pattern.match(sih4).group("start"))

    def get_sih4_end(self):
        if self.sih4:
            sih4 = self.sih4.strip('"')
            if gradient_pattern.match(sih4).group("end"):
                return decimal.Decimal(gradient_pattern.match(sih4).group("end"))

    def get_h2_mfc(self):
        h2 = max(self.get_h2_start(), self.get_h2_end())
        if h2 is not None:
            mfc_limit = 500 if self.get_date() < datetime.date(2010, 5, 28) else 1500
            return 2 if h2 > mfc_limit else 1

    def get_sih4_mfc(self):
        sih4 = max(self.get_sih4_start(), self.get_sih4_end())
        if sih4 is not None:
            return 2 if sih4 > 50 else 1

    def get_tmb(self):
        return (decimal.Decimal(self.tmb), 1 if float(self.tmb) <= 10 else 2) if self.tmb else (None, 1)

    def get_ch4(self):
        return decimal.Decimal(self.ch4) if self.ch4 else None

    def get_co2(self):
        return decimal.Decimal(self.co2) if self.co2 else None

    def get_ph3_start(self):
        if self.ph3:
            ph3 = self.ph3.strip('"')
            return decimal.Decimal(gradient_pattern.match(ph3).group("start"))

    def get_ph3_end(self):
        if self.ph3:
            ph3 = self.ph3.strip('"')
            if gradient_pattern.match(ph3).group("end"):
                return decimal.Decimal(gradient_pattern.match(ph3).group("end"))

    def get_ph3_mfc(self):
        ph3 = max(self.get_ph3_start(), self.get_ph3_end())
        if ph3 is not None:
            return 2 if ph3 > 10 else 1

    def get_additional_gas(self):
        return self.additional_gas

    def get_additional_gas_flow(self):
        if self.additional_gas_flow and two_value_pattern.match(self.additional_gas_flow).group("second"):
            self.comments += "\nsecond {gas} gas flow: {gas_flow} sccm".format(gas=self.additional_gas,
                                gas_flow=two_value_pattern.match(self.additional_gas_flow).group("second"))
        return decimal.Decimal(two_value_pattern.match(self.additional_gas_flow).group("first")) \
            if self.additional_gas_flow else None

    def get_time(self):
        if "?" in self.time:
            self.time = None
            self.comments += "\ntime unknown"
        try:
            return int(float(self.time)) if self.time else 0
        except ValueError:
            self.comments += "\ntime: {0} s".format(self.time.strip('"'))
            return 0

    def get_pressure(self):
        return decimal.Decimal(self.pressure) if self.pressure else decimal.Decimal('0')

    def get_power(self):
        power = self.power.strip('"')
        return (decimal.Decimal(two_value_pattern.match(power).group("first")),
                decimal.Decimal(two_value_pattern.match(power).group("second"))
                if two_value_pattern.match(power).group("second") else None) \
                if power else (decimal.Decimal('0'), None)

    def get_frequency(self):
        return decimal.Decimal(self.hf_frequency)

    def get_electrodes_distance(self):
        return decimal.Decimal(self.electrodes_distance) if self.electrodes_distance else None

    def get_substrate_temperature(self):
        temperature_substrate = self.temperature_substrate
        if "kalt" in temperature_substrate:
            temperature_substrate = 20
        elif "-" in temperature_substrate:
            self.comments += "\nsubstrate temperature: {0} ℃".format(temperature_substrate)
            temperature_substrate = None
        return int(float(temperature_substrate)) if temperature_substrate else None

    def get_heater_temperature(self):
        return int(self.temperature_heater) if self.temperature_heater else None

    def get_depo_temperature(self):
        return int(self.temperature_heater_depo.replace("~", "")) if self.temperature_heater_depo else None

    def get_substrate_size(self):
        return None if "Übrig" in self.substrate_size or "Dummy" in self.substrate_size \
            else self.substrate_size.strip('"')[:5]

    def get_substrate(self):
        return None if "Übrig" in self.substrate else self.substrate.strip('"')

    def get_carrier(self):
        return "dummy" if "Dummy" in self.substrate_size else None

    def get_suffixes(self):
        glasses = int(self.glasses) if self.glasses else 1
        if self.suffixes and len(self.suffixes.strip('"')) >= glasses:
            return self.suffixes.strip('"').split(",")
        return range(1, glasses + 1)

    def get_power_reflected(self):
        power_reflected = self.power_reflected.strip('"')
        return (decimal.Decimal(two_value_pattern.match(power_reflected).group("first")),
                decimal.Decimal(two_value_pattern.match(power_reflected).group("second"))
                if two_value_pattern.match(power_reflected).group("second") else None) \
                if power_reflected else (None, None)

    def get_cl(self):
        cl = self.cl.strip('"')
        return (int(float(two_value_pattern.match(cl).group("first"))),
                int(float(two_value_pattern.match(cl).group("second")))
                if two_value_pattern.match(cl).group("second") else None) \
                if cl else (None, None)

    def get_ct(self):
        ct = self.ct.strip('"')
        return (int(float(two_value_pattern.match(ct).group("first"))),
                int(float(two_value_pattern.match(ct).group("second")))
                if two_value_pattern.match(ct).group("second") else None) \
                if ct else (None, None)

    def get_udc(self):
        udc = self.u_dc.strip('"')
        return (decimal.Decimal(two_value_pattern.match(udc).group("first")),
                decimal.Decimal(two_value_pattern.match(udc).group("second"))
                if two_value_pattern.match(udc).group("second") else None) \
                if udc else (None, None)

    def get_base_pressure(self):
        return float(self.base_pressure.strip('"').strip("~")) if self.base_pressure else None

    def get_comments(self):
        return sanitize_for_markdown(unicode(self.comments.strip('"'))) if self.comments.strip('"') else ""


login(credentials["crawlers_login"], credentials["crawlers_password"], testserver=True)
for data_file in ["LADA_data_2009.csv", "LADA_data_2010.csv", "LADA_data_2011.csv"]:
    status_message = ""
    lada_layer_data = LADAData()
    lada_deposition = None
    continue_layer = False
    lada_layer = None
    previous_layer_type = ""
    lines = read_lines(data_file)[2:]
    for line_counter, line in enumerate(lines):
        try:
            lada_layer_data.layer_number, lada_layer_data.date, lada_layer_data.operator, \
            lada_layer_data.layer_type, lada_layer_data.chamber, lada_layer_data.v_lq, \
            lada_layer_data.pendulum_lq, lada_layer_data.h2, lada_layer_data.sih4, _, \
            lada_layer_data.tmb, lada_layer_data.ch4, lada_layer_data.co2, lada_layer_data.ph3, \
            lada_layer_data.additional_gas, lada_layer_data.additional_gas_flow, lada_layer_data.time, \
            lada_layer_data.pressure, lada_layer_data.power, _, lada_layer_data.hf_frequency, \
            lada_layer_data.electrodes_distance, lada_layer_data.temperature_substrate, \
            lada_layer_data.temperature_heater, lada_layer_data.temperature_heater_depo, \
            lada_layer_data.substrate_size, lada_layer_data.substrate, lada_layer_data.glasses, \
            lada_layer_data.power_reflected, lada_layer_data.cl, lada_layer_data.ct, lada_layer_data.u_dc, \
            lada_layer_data.base_pressure, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, \
            _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, _, lada_layer_data.suffixes, \
            lada_layer_data.comments = line.split("\t")[:72]
        except ValueError:
            logging.error("Skipped line #{0}".format(line_counter + 3))
            continue
        if not lada_layer_data.get_deposition_number() and not lada_layer_data.get_datetime():
            logging.info("Start next deposition")
            lada_deposition = LADADeposition()
            lada_deposition.comments = "BEFORE: {0}".format(lada_layer_data.get_comments()) \
                if lada_layer_data.get_comments() else ""
        else:
            if not lada_deposition.sample_ids:
                lada_deposition.sample_ids = [get_or_create_sample("{name}-{suffix}".format(
                                                name=lada_layer_data.get_deposition_number(), suffix=i),
                                                lada_layer_data.get_substrate(), lada_layer_data.get_datetime(),
                                                add_zno_warning=True if lada_layer_data.get_substrate() == "ZnO" else False)
                                              for i in lada_layer_data.get_suffixes()]
            if not lada_deposition.operator:
                lada_deposition.operator = lada_layer_data.get_operator()
            if not lada_deposition.customer:
                lada_deposition.customer = lada_layer_data.get_operator()
            if not lada_deposition.number:
                lada_deposition.number = lada_layer_data.get_deposition_number()
            if not lada_deposition.timestamp:
                lada_deposition.timestamp = lada_layer_data.get_datetime()
                lada_deposition.timestamp_inaccuracy = 3
            if not lada_deposition.substrate_size:
                lada_deposition.substrate_size = lada_layer_data.get_substrate_size()
            if continue_layer:
                logging.info("Found dublicated number {0} in deposition {1}".format(lada_layer_data.get_layer_number(),
                                                                                    lada_deposition.number))
                if not lada_layer.h2_1 == lada_layer_data.get_h2_start():
                    lada_layer.h2_2 = lada_layer_data.get_h2_start()
                    lada_layer.h2_2_end = lada_layer_data.get_h2_end()
                    lada_layer.h2_mfc_number_2 = lada_layer_data.get_h2_mfc()
                if not lada_layer.sih4_1 == lada_layer_data.get_sih4_start():
                    lada_layer.sih4_2 = lada_layer_data.get_sih4_start()
                    lada_layer.sih4_2_end = lada_layer_data.get_sih4_end()
                    lada_layer.sih4_mfc_number_2 = lada_layer_data.get_sih4_mfc()
                lada_layer.time_2 = lada_layer_data.get_time()
                lada_layer.comments += "\n{0}".format(lada_layer_data.get_comments()) if lada_layer_data.get_comments() else ""
                lada_layer.comments += "\nLayer type changed from {0} to {1}\n  ".format(previous_layer_type,
                            lada_layer_data.get_layer_type()) if previous_layer_type != lada_layer_data.get_layer_type() else ""
            else:
                lada_layer = LADALayer(lada_deposition)
                lada_layer.layer_number = lada_layer_data.get_layer_number()
                lada_layer.additional_gas = lada_layer_data.get_additional_gas()
                lada_layer.additional_gas_flow = lada_layer_data.get_additional_gas_flow()
                lada_layer.base_pressure = lada_layer_data.get_base_pressure()
                lada_layer.carrier = lada_layer_data.get_carrier()
                lada_layer.ch4 = lada_layer_data.get_ch4()
                lada_layer.chamber = lada_layer_data.get_chamber()
                lada_layer.cl_1, lada_layer.cl_2 = lada_layer_data.get_cl()
                lada_layer.co2 = lada_layer_data.get_co2()
                lada_layer.comments = lada_layer_data.get_comments()
                lada_layer.ct_1, lada_layer.ct_2 = lada_layer_data.get_ct()
                lada_layer.date = lada_layer_data.get_date()
                lada_layer.electrodes_distance = lada_layer_data.get_electrodes_distance()
                lada_layer.h2_1 = lada_layer_data.get_h2_start()
                lada_layer.h2_1_end = lada_layer_data.get_h2_end()
                lada_layer.h2_mfc_number_1 = lada_layer_data.get_h2_mfc()
                lada_layer.hf_frequency = lada_layer_data.get_frequency()
                lada_layer.layer_type = lada_layer_data.get_layer_type()
                lada_layer.pendulum_lq = lada_layer_data.get_pendulum_lq()
                if lada_layer_data.get_ph3_mfc() == 1:
                    lada_layer.ph3_1 = lada_layer_data.get_ph3_start()
                    lada_layer.ph3_1_end = lada_layer_data.get_ph3_end()
                else:
                    lada_layer.ph3_2 = lada_layer_data.get_ph3_start()
                    lada_layer.ph3_2_end = lada_layer_data.get_ph3_end()
                lada_layer.power_1, lada_layer.power_2 = lada_layer_data.get_power()
                lada_layer.power_reflected_1, lada_layer.power_reflected_2 = lada_layer_data.get_power_reflected()
                lada_layer.pressure = lada_layer_data.get_pressure()
                lada_layer.sih4_1 = lada_layer_data.get_sih4_start()
                lada_layer.sih4_1_end = lada_layer_data.get_sih4_end()
                lada_layer.sih4_mfc_number_1 = lada_layer_data.get_sih4_mfc()
                lada_layer.temperature_heater = lada_layer_data.get_heater_temperature()
                lada_layer.temperature_heater_depo = lada_layer_data.get_depo_temperature()
                lada_layer.temperature_substrate = lada_layer_data.get_substrate_temperature()
                lada_layer.time_1 = lada_layer_data.get_time()
                if lada_layer_data.get_tmb()[1] == 1:
                    lada_layer.tmb_1 = lada_layer_data.get_tmb()[0]
                else:
                    lada_layer.tmb_2 = lada_layer_data.get_tmb()[0]
                lada_layer.u_dc = lada_layer_data.get_udc()
                lada_layer.v_lq = lada_layer_data.get_vlq()
                lada_layer.plasma_stop = True

                if lada_layer_data.get_deposition_number() == "10D-486":
                    lada_deposition.comments = "Layer 10D-490 is not included.\n  " + lada_deposition.comments
                elif lada_layer_data.get_deposition_number() in ["11D-838", "11D-898"]:
                    lada_layer.comments += "\n  pressure change from 0.65 mbar to 1.5 mbar."
                elif lada_layer_data.get_deposition_number() == "11D-1850":
                    lada_layer.comments += "\n  pressure change from 4 mbar to 12.5 mbar."

            if not lines[line_counter + 1].strip() \
                or (not lines[line_counter + 1].split("\t")[0].strip('"') and not lines[line_counter + 1].split("\t")[1]):
                try:
                    lada_deposition.submit()
                    connection.open("change_my_samples", {"remove": comma_separated_ids(lada_deposition.sample_ids)})
                except ChantalError as e:
                    logging.error("{0}".format(e))
            else:
                previous_layer_type = lada_layer_data.get_layer_type()
        continue_layer = True if lines[line_counter + 1].split("\t")[0] == lada_layer_data.layer_number else False
logout()
