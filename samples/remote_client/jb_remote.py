#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
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
import six

import urllib, urllib2, cookielib, json, logging
import datetime, re, time, random

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='jb_remote.log',
                    filemode='w')

__all__ = ["login", "logout", "new_samples", "SixChamberDeposition", "SixChamberLayer", "SixChamberChannel",
           "LargeAreaDeposition", "LargeAreaLayer", "rename_after_deposition", "PDSMeasurement", "get_or_create_sample",
           "SmallClusterToolDeposition", "SmallClusterToolHotwireLayer", "SmallClusterToolPECVDLayer"]


def quote_header(value):
    if isinstance(value, bool):
        return "on" if value else None
    return six.text_type(value).encode("utf-8")


class ResponseError(Exception):
    pass


class JuliaBaseConnection(object):
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
    opener.addheaders = [("User-agent", "JuliaBase-Remote/0.1")]

    def __init__(self, jb_url="http://juliabase.ipv.kfa-juelich.de/"):
        self.root_url = jb_url
        self.username = None
        self.primary_keys = None

    def open(self, relative_url, data=None, https=False):
        root_url = self.root_url if not https else "https" + self.root_url[4:]
        if data is not None:
            cleaned_data = {}
            for key, value in data.items():
                key = quote_header(key)
                if value is not None:
                    if not isinstance(value, list):
                        quoted_header = quote_header(value)
                        if quoted_header:
                            cleaned_data[key] = quoted_header
                    else:
                        cleaned_list = [quote_header(item) for item in value if value is not None]
                        if cleaned_list:
                            cleaned_data[key] = cleaned_list
            max_cycles = 10
            while max_cycles > 0:
                max_cycles -= 1
                try:
                    response = self.opener.open(root_url + relative_url, urllib.urlencode(cleaned_data, doseq=True))
                except urllib2.HTTPError as e:
                    if max_cycles == 0:
                        text = e.read()
                        logfile = open("jb_remote.html", "wb")
                        print >> logfile, text
                        logfile.close()
                        raise
                    time.sleep(3 * random.random())
                else:
                    break
        else:
            response = self.opener.open(root_url + relative_url)
        is_pickled = response.info()["Content-Type"].startswith("application/json")
        if is_pickled:
            return json.loads(response.read())
        else:
            logging.error("Resonse was not in JSON format.  Probably failed validation.")
            text = response.read()
            logfile = open("jb_remote.html", "wb")
            logfile.write(text)
            logfile.close()
            raise ResponseError("Response was not in JSON format!")

    def login(self, username, password):
        self.username = username
        if not self.open("login_remote_client", {"username": username, "password": password}, https=True):
            logging.error("Login failed.")
            raise ResponseError("Login failed")
        # FixMe: Test whether login was successful
        self.primary_keys = self.open("primary_keys?topics=*&users=*")

    def logout(self):
        if not self.open("logout_remote_client"):
            logging.error("Logout failed.")
            raise ResponseError("Logout failed")


connection = JuliaBaseConnection()


def login(username, password):
    connection.login(username, password)
    logging.info("Successfully logged-in as %s." % username)


def logout():
    connection.logout()
    logging.info("Successfully logged-out.")


def new_samples(number_of_samples, current_location, substrate="asahi-u", timestamp=None, timestamp_inaccuracy=None,
                purpose=None, tags=None, topic=None, substrate_comments=None):
    samples = connection.open("samples/add/",
                              {"number_of_samples": number_of_samples,
                               "current_location": current_location,
                               "timestamp": timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               "timestamp_inaccuracy": timestamp_inaccuracy or 0,
                               "substrate": substrate,
                               "substrate_comments": substrate_comments,
                               "purpose": purpose,
                               "tags": tags,
                               "topic": connection.primary_keys["topics"].get(topic),
                               "currently_responsible_person":
                                   connection.primary_keys["users"][connection.username]})
    logging.info("Successfully created %d samples with the ids %s." % (len(samples), ",".join(str(id_) for id_ in samples)))
    return samples


class SixChamberDeposition(object):

    def __init__(self, sample_ids):
        self.sample_ids = sample_ids
        self.number = self.carrier = self.operator = self.timestamp = self.comments = None
        self.timestamp_inaccuracy = 0
        self.layers = []

    def submit(self):
        # FixMe: Assure that sample is in MySamples
        #
        # Returns the deposition number if succeeded
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = json.loads(self.opener.open(self.root_url + "next_deposition_number/B").read())
        data = {"number": self.number,
                "carrier": self.carrier,
                "operator": connection.primary_keys["users"][self.operator],
                "timestamp": self.timestamp,
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_deposited_from_my_samples": True}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        result = connection.open("6-chamber_depositions/add/", data)
        logging.info("Successfully added 6-chamber deposition %s." % self.number)
        return result


class SixChamberLayer(object):

    def __init__(self, deposition):
        self.deposition = deposition
        deposition.layers.append(self)
        self.chamber = self.pressure = self.time = \
            self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
            self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
            self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
            self.deposition_frequency = self.deposition_power = self.base_pressure = None
        self.channels = []

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "chamber": self.chamber,
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_electrode_distance": self.substrate_electrode_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "plasma_start_power": self.plasma_start_power,
                prefix + "plasma_start_with_carrier": self.plasma_start_with_carrier,
                prefix + "deposition_frequency": self.deposition_frequency,
                prefix + "deposition_power": self.deposition_power,
                prefix + "base_pressure": self.base_pressure}
        for channel_index, channel in enumerate(self.channels):
            data.update(channel.get_data(layer_index, channel_index))
        return data


class SixChamberChannel(object):

    def __init__(self, layer):
        self.layer = layer
        layer.channels.append(self)
        self.number = self.gas = self.flow_rate = None

    def get_data(self, layer_index, channel_index):
        prefix = "%d_%d-" % (layer_index, channel_index)
        return {prefix + "number": self.number, prefix + "gas": self.gas, prefix + "flow_rate": self.flow_rate}



class LargeAreaDeposition(object):
    deposition_prefix = "%02dL-" % (datetime.date.today().year % 100)
    deposition_number_pattern = re.compile(r"\d\dL-(?P<number>\d+)$")

    def __init__(self, sample_ids):
        self.sample_ids = sample_ids
        self.number = self.operator = self.timestamp = self.comments = None
        self.timestamp_inaccuracy = 0
        self.layers = []

    def submit(self):
        # FixMe: Assure that sample is in MySamples
        #
        # Returns the deposition number if succeeded
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            next_number = connection.open("next_deposition_number/L")
            number_base = int(self.deposition_number_pattern.match(next_number).group("number")) - 1
            self.number = self.deposition_prefix + "%03d" % (number_base + len(self.layers))
        else:
            number_base = int(self.deposition_number_pattern.match(self.number).group("number")) - 1
        data = {"number": self.number,
                "operator": connection.primary_keys["users"][self.operator],
                "timestamp": self.timestamp,
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_deposited_from_my_samples": True}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index + number_base + 1, layer_index))
        result = connection.open("large-area_depositions/add/", data)
        logging.info("Successfully added large area deposition %s." % self.number)
        return result


class LargeAreaLayer(object):

    def __init__(self, deposition):
        self.deposition = deposition
        deposition.layers.append(self)
        self.date = self.layer_type = self.station = self.sih4 = self.h2 = self.tmb = self.ch4 = \
            self.co2 = self.ph3 = self.power = self.pressure = self.temperature = self.hf_frequency = self.time = \
            self.dc_bias = self.electrode = self.electrodes_distance = None

    def get_data(self, layer_number, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": self.number or layer_number,
                prefix + "date": self.date,
                prefix + "layer_type": self.layer_type,
                prefix + "station": self.station,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2,
                prefix + "tmb": self.tmb,
                prefix + "ch4": self.ch4,
                prefix + "co2": self.co2,
                prefix + "ph3": self.ph3,
                prefix + "power": self.power,
                prefix + "pressure": self.pressure,
                prefix + "temperature": self.temperature,
                prefix + "hf_frequency": self.hf_frequency,
                prefix + "time": self.time,
                prefix + "dc_bias": self.dc_bias,
                prefix + "electrode": self.electrode,
                prefix + "electrodes_distance": self.electrodes_distance}
        return data


class SmallClusterToolDeposition(object):

    def __init__(self, sample_ids):
        self.sample_ids = sample_ids
        self.number = self.operator = self.timestamp = self.comments = None
        self.timestamp_inaccuracy = 0
        self.layers = []

    def submit(self):
        # FixMe: Assure that sample is in MySamples
        #
        # Returns the deposition number if succeeded
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/C")
        data = {"number": self.number,
                "operator": connection.primary_keys["users"][self.operator],
                "timestamp": self.timestamp,
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_deposited_from_my_samples": True}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        result = connection.open("small_cluster_tool_depositions/add/", data)
        logging.info("Successfully added small cluster toll deposition %s." % self.number)
        return result


class SmallClusterToolHotwireLayer(object):

    def __init__(self, deposition):
        self.deposition = deposition
        deposition.layers.append(self)
        self.pressure = self.time = \
            self.substrate_wire_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
            self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
            self.transfer_out_of_chamber = self.wire_material = self.voltage = \
            self.filament_temperature = self.current = self.base_pressure = None
        self.sih4 = self.h2 = self.ph3_sih4 = self.tmb_he = self.b2h6_h2 = self.ch4 = self.co2 = self.geh4 = self.ar = \
            self.si2h6 = self.ph3_h2 = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "hotwire",
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_wire_distance": self.substrate_wire_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "wire_material": self.wire_material,
                prefix + "voltage": self.voltage,
                prefix + "filament_temperature": self.filament_temperature,
                prefix + "current": self.current,
                prefix + "base_pressure": self.base_pressure,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2,
                prefix + "ph3_sih4": self.ph3_sih4,
                prefix + "tmb_he": self.tmb_he,
                prefix + "b2h6_h2": self.b2h6_h2,
                prefix + "ch4": self.ch4,
                prefix + "co2": self.co2,
                prefix + "geh4": self.geh4,
                prefix + "ar": self.ar,
                prefix + "si2h6": self.si2h6,
                prefix + "ph3_h2": self.ph3_h2}
        return data


class SmallClusterToolPECVDLayer(object):

    def __init__(self, deposition):
        self.deposition = deposition
        deposition.layers.append(self)
        self.chamber = self.pressure = self.time = \
            self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
            self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
            self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
            self.deposition_frequency = self.deposition_power = self.base_pressure = None
        self.sih4 = self.h2 = self.ph3_sih4 = self.tmb_he = self.b2h6_h2 = self.ch4 = self.co2 = self.geh4 = self.ar = \
            self.si2h6 = self.ph3_h2 = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "PECVD",
                prefix + "chamber": self.chamber,
                prefix + "pressure": self.pressure,
                prefix + "time": self.time,
                prefix + "substrate_electrode_distance": self.substrate_electrode_distance,
                prefix + "comments": self.comments,
                prefix + "transfer_in_chamber": self.transfer_in_chamber,
                prefix + "pre_heat": self.pre_heat,
                prefix + "gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix + "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix + "gas_pre_heat_time": self.gas_pre_heat_time,
                prefix + "heating_temperature": self.heating_temperature,
                prefix + "transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix + "plasma_start_power": self.plasma_start_power,
                prefix + "plasma_start_with_carrier": self.plasma_start_with_carrier,
                prefix + "deposition_frequency": self.deposition_frequency,
                prefix + "deposition_power": self.deposition_power,
                prefix + "base_pressure": self.base_pressure,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2,
                prefix + "ph3_sih4": self.ph3_sih4,
                prefix + "tmb_he": self.tmb_he,
                prefix + "b2h6_h2": self.b2h6_h2,
                prefix + "ch4": self.ch4,
                prefix + "co2": self.co2,
                prefix + "geh4": self.geh4,
                prefix + "ar": self.ar,
                prefix + "si2h6": self.si2h6,
                prefix + "ph3_h2": self.ph3_h2}
        return data


def rename_after_deposition(deposition_number, samples):
    data = {}
    for i, id_ in enumerate(samples):
        data["%d-sample" % i] = id_
        data["%d-number_of_pieces" % i] = 1
        data["0-new_name"] = data["%d_0-new_name" % i] = samples[id_]
    return connection.open("depositions/split_and_rename_samples/" + deposition_number, data)


class PDSMeasurement(object):

    def __init__(self, sample_id):
        self.sample_id = sample_id
        self.number = self.operator = self.timestamp = self.comments = None
        self.timestamp_inaccuracy = 0
        self.raw_datafile = self.evaluated_datafile = None

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        result = connection.open("samples/by_id/%s" % self.sample_id, {"is_my_sample": True})
        assert result
        data = {"number": self.number,
                "sample": self.sample_id,
                "timestamp": self.timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": connection.primary_keys["users"][self.operator],
                "raw_datafile": self.raw_datafile,
                "evaluated_datafile": self.evaluated_datafile,
                "comments": self.comments,
                "remove_measured_from_my_samples": True}
        return connection.open("pds_measurements/add/", data)


def add_century(two_digit_year):
    two_digit_year = int(two_digit_year)
    if two_digit_year < 70:
        return 2000 + two_digit_year
    else:
        return 1900 + two_digit_year


class QuirkySampleError(Exception):
    pass


quirky_deposition_number_pattern = re.compile(r"(?P<year>\d\d)(?P<letter>[BVHLCSbvhlcs])-?(?P<number>\d{1,4})"
                                              r"(?P<suffix>[-A-Za-z_/][-A-Za-z_/0-9]*)?$")
quirky_sample_name_pattern = re.compile(r"(?P<year>\d\d)-(?P<initials>[A-Za-z]{2}(?:[A-Za-z]{0,2}|[A-Za-z]\d|\d{0,2}))-"

                                        r"(?P<suffix>[A-Za-z0-9][-A-Za-z_/0-9]*)?$")
def normalize_sample_name(sample_name):
    result_dict = {}
    match = quirky_deposition_number_pattern.match(sample_name)
    if match:
        parts = match.groupdict("")
        parts["number"] = int(parts["number"])
        parts["letter"] = parts["letter"].upper()
        deposition_number = "%(year)s%(letter)s-%(number)03d" % parts
        result_dict.update({"year": add_century(parts["year"]), "letter": parts["letter"], "number": parts["number"],
                            "deposition_number": deposition_number})
        if parts["suffix"]:
            result_dict["suffix"] = parts["suffix"]
        sample_name = deposition_number + parts["suffix"]
    else:
        match = quirky_sample_name_pattern.match(sample_name)
        if match:
            parts = match.groupdict("")
            parts["number"] = int(parts["number"])
            parts["initials"] = parts["initials"].upper()
            result_dict.update({"year": add_century(parts["year"]), "initials": parts["initials"]})
            if parts["suffix"]:
                result_dict["suffix"] = parts["suffix"]
            sample_name = "%(year)s-%(initials)s-%(suffix)s" % parts
        else:
            raise QuirkySampleError("Sample name is too quirky to normalize")
    return sample_name, result_dict


def get_or_create_sample(sample_name):
    try:
        sample_name, name_info = normalize_sample_name(sample_name)
    except QuirkySampleError:
        # FixMe: Convert legacy names to "08-TB-XXX"-like names whenever
        # possible
        return None
    sample_id = connection.open("primary_keys?samples=" + sample_name)["samples"].get(sample_name)
    if sample_id is None:
        if "deposition_number" in name_info:
            parent_name = name_info["deposition_number"]
            parent_id = connection.open("primary_keys?samples=" + parent_name)["samples"].get(sample_name)
            if not parent_id:
                return None
            latest_split = connection.open("latest_split/" + parent_name)
            data = {"0-new_name": sample_name, "1-new_name": ""}
            if latest_split is None:
                new_ids = connection.open("samples/%s/split/" % parent_name, data)
            else:
                new_ids = connection.open("resplit/%d" % latest_split, data)
            sample_id = new_ids[sample_name]
        else:
            # FixMe: Create completely new sample with "08-TB-XXX"-like name
            pass
    return sample_id
