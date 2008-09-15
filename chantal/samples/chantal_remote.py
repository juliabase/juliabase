#!/usr/bin/env python
# -*- coding: utf-8 -*-

import mechanize
from elementtree.ElementTree import XML
import datetime

class ChantalConnection(object):
    def __init__(self, username, password, chantal_url="http://bob.ipv.kfa-juelich.de/chantal/"):
        self.root_url = chantal_url
        self.browser = mechanize.Browser()
        self.browser.set_handle_robots(False)
        self.username = username
        self.controls = {}
        self.selection_options = {}

        # Login
        self.browser.open(self.root_url+"login")
        self.browser.select_form(nr=0)
        self.browser["username"] = username
        self.browser["password"] = password
        self.browser.submit()
        # FixMe: Test whether login was successful
    def parse_form_data(self):
        self.controls.clear()
        self.selection_options.clear()
        try:
            self.browser.select_form(nr=0)
        except mechanize._mechanize.FormNotFoundError:
            return
        for control in self.browser.form.controls:
            self.controls[control.name] = control
            if control.type == "select":
                self.selection_options[control.name] = {}
                for option in control.items:
                    self.selection_options[control.name][option.attrs["contents"]] = option.attrs["value"]
    def open(self, relative_url):
        response = self.browser.open(self.root_url+relative_url)
        self.parse_form_data()
    def submit(self, get_success_report=True):
        response = self.browser.submit()
        self.parse_form_data()
        text = response.read()
        logfile = open("toll.log", "wb")
        print>>logfile, text
        logfile.close()
        if get_success_report:
            tree = XML(text)
            for meta in tree.getiterator("{http://www.w3.org/1999/xhtml}meta"):
                if meta.attrib.get("name") == "success-report":
                    return meta.attrib["content"]
            for div in tree.getiterator("{http://www.w3.org/1999/xhtml}div"):
                if div.attrib.get("class") == "success-report":
                    return div.text
            raise Exception("Didn't find a success report")
    def set_form_data(self, form_dict, prefix=None):
        def find_value_for_option(name, option):
            if option is not None:
                try:
                    return self.selection_options[name][unicode(option)]
                except KeyError:
                    return None
            return None
        def build_selection_list(name, options):
            list_ = [find_value_for_option(name, option) for option in options]
            return [item for item in list_ if item is not None]

        if prefix:
            prefix += u"-"
        for key, value in form_dict.iteritems():
            if prefix:
                key = prefix + key
            if value is not None:
                if self.controls[key].type == "text":
                    self.browser[key] = unicode(value)
                elif self.controls[key].type == "select":
                    if self.controls[key].multiple:
                        self.browser[key] = build_selection_list(key, value)
                    else:
                        value = find_value_for_option(key, value)
                        if value is not None:
                            self.browser[key] = [value]
    def get_new_samples(self, number_of_samples, current_location, substrate=u"ASAHI-U",
                        purpose=None, tags=None, group=None):
        self.open("samples/add/")
        self.set_form_data({"number_of_samples": number_of_samples,
                            "current_location": current_location,
                            "substrate": substrate,
                            "purpose": purpose,
                            "tags": tags,
                            "group": group,
                            "currently_responsible_person": self.username})
        return self.submit().split(",")
    def __del__(self):
        self.browser.open(self.root_url+"logout")

class SixChamberDeposition(object):
    def __init__(self, sample_name=None):
        self.sample_name = sample_name
        self.number = self.carrier = self.operator = self.timestamp = self.comments = None
        self.layers = []
    def submit(self, connection):
        if not self.sample_name:
            self.sample_name = connection.get_new_samples(1, u"unknown due to legacy data")
        # FixMe: Assure that sample is in MySamples
        connection.open("6-chamber_depositions/add/")
        connection.browser["structural-change-add-layers"] = unicode(len(self.layers))
        connection.submit(get_success_report=False)
        for i, layer in enumerate(self.layers):
            connection.browser["structural-change-add-channels-for-layerindex-%d" % i] = unicode(len(layer.channels))
        connection.submit(get_success_report=False)
        date, time = self.timestamp.split(" ")
        if not self.operator:
            self.operator = connection.username
        connection.set_form_data({"number": self.number,
                                  "carrier": self.carrier,
                                  "operator": self.operator,
                                  "timestamp_0": date,
                                  "timestamp_1": time,
                                  "comments": self.comments,
                                  "sample_list": self.sample_name})
        for i, layer in enumerate(self.layers):
            layer.submit(connection, i)
        connection.submit()

class SixChamberLayer(object):
    def __init__(self, deposition):
        self.deposition = deposition
        deposition.layers.append(self)
        self.number = self.chamber = self.chamber = self.pressure = self.time = \
            self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
            self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
            self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
            self.deposition_frequency = self.deposition_power = self.base_pressure = None
        self.channels = []
    def submit(self, connection, index):
        connection.set_form_data({"number": self.number,
                                  "chamber": self.chamber,
                                  "pressure": self.pressure,
                                  "time": self.time,
                                  "substrate_electrode_distance": self.substrate_electrode_distance,
                                  "comments": self.comments,
                                  "transfer_in_chamber": self.transfer_in_chamber,
                                  "pre_heat": self.pre_heat,
                                  "gas_pre_heat_gas": self.gas_pre_heat_gas,
                                  "gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                                  "gas_pre_heat_time": self.gas_pre_heat_time,
                                  "heating_temperature": self.heating_temperature,
                                  "transfer_out_of_chamber": self.transfer_out_of_chamber,
                                  "plasma_start_power": self.plasma_start_power,
                                  "plasma_start_with_carrier": self.plasma_start_with_carrier,
                                  "deposition_frequency": self.deposition_frequency,
                                  "deposition_power": self.deposition_power,
                                  "base_pressure": self.base_pressure}, prefix=unicode(index))
        for i, channel in enumerate(self.channels):
            channel.submit(connection, index, i)

class SixChamberChannel(object):
    def __init__(self, layer):
        self.layer = layer
        layer.channels.append(self)
        self.number = self.gas = self.flow_rate = None
    def submit(self, connection, layer_index, index):
        connection.set_form_data({"number": self.number,
                                  "gas": self.gas,
                                  "flow_rate": self.flow_rate}, prefix="%d_%d" % (layer_index, index))

connection = ChantalConnection("bronger", "*******", "http://127.0.0.1:8000/")

six_chamber_deposition = SixChamberDeposition()
six_chamber_deposition.timestamp = "2008-09-15 22:29:00"

layer = SixChamberLayer(six_chamber_deposition)
layer.chamber = "#1"

channel1 = SixChamberChannel(layer)
channel1.number = 1
channel1.gas = "SiH4"
channel1.flow_rate = "1"

channel2 = SixChamberChannel(layer)
channel2.number = 2
channel2.gas = "SiH4"
channel2.flow_rate = "2"

channel3 = SixChamberChannel(layer)
channel3.number = 3
channel3.gas = "SiH4"
channel3.flow_rate = "3"

six_chamber_deposition.layers.extend([layer, layer])

for i in range(10):
    six_chamber_deposition.submit(connection)
    six_chamber_deposition.sample_name = None
