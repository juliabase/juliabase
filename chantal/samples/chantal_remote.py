#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, urllib2, cookielib, pickle
from elementtree.ElementTree import XML
import datetime

class ChantalHTTPProcessor(urllib2.BaseHandler):
    user_agent = "Chantal-Remote 0.1"
    def http_request(self, request):
        request.add_header("User-Agent", self.user_agent)
        return request

def quote_header(value):
    return unicode(value).encode("utf-8")

class ChantalConnection(object):
    opener = urllib2.build_opener(ChantalHTTPProcessor())
    def __init__(self, username, password, chantal_url="http://bob.ipv.kfa-juelich.de/chantal/"):
        self.root_url = chantal_url
        self.username = username

        # Login
        self.open("login", {"username": username, "password": password})
        # FixMe: Test whether login was successful
        self.primary_keys = pickle.load(self.opener.open(self.root_url+"primary_keys?groups=*&users=*"))
    def open(self, relative_url, data=None, parse_response="None"):
        # `parse_response` may be ``None``, "html", or "pickle"
        if data is not None:
            cleaned_data = {}
            for key, value in data.iteritems():
                key = quote_header(key)
                if value is not None:
                    if not isinstance(value, list):
                        cleaned_data[key] = quote_header(value)
                    else:
                        cleaned_list = [quote_header(item) for item in value if value is not None]
                        if cleaned_list:
                            cleaned_data[key] = cleaned_list
            try:
                response = self.opener.open(self.root_url+relative_url, urllib.urlencode(cleaned_data, doseq=True))
            except urllib2.HTTPError, e:
                text = e.read()
                logfile = open("/home/bronger/public_html/toll.html", "wb")
                print>>logfile, text
                logfile.close()
                raise
        else:
            response = self.opener.open(self.root_url+relative_url)
        if parse_response == "pickle":
            return pickle.load(response)
        elif parse_response == "html":
            text = response.read()
            logfile = open("toll.log", "wb")
            print>>logfile, text
            logfile.close()
            tree = XML(text)
            for div in tree.getiterator("{http://www.w3.org/1999/xhtml}div"):
                if div.attrib.get("class") == "success-report":
                    return div.text
            raise Exception("Didn't find a success report")
    def get_new_samples(self, number_of_samples, current_location, substrate=u"asahi-u",
                        purpose=None, tags=None, group=None):
        return self.open("samples/add/", {"number_of_samples": number_of_samples,
                                          "current_location": current_location,
                                          "substrate": substrate,
                                          "purpose": purpose,
                                          "tags": tags,
                                          "group": self.primary_keys["groups"].get(group),
                                          "currently_responsible_person": self.primary_keys["users"].get(self.username)},
                         parse_response="pickle")
    def close(self):
        self.open("logout")

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
print connection.get_new_samples(1, "Hall lab")
connection.close()

# six_chamber_deposition = SixChamberDeposition()
# six_chamber_deposition.timestamp = "2008-09-15 22:29:00"

# layer = SixChamberLayer(six_chamber_deposition)
# layer.chamber = "#1"

# channel1 = SixChamberChannel(layer)
# channel1.number = 1
# channel1.gas = "SiH4"
# channel1.flow_rate = "1"

# channel2 = SixChamberChannel(layer)
# channel2.number = 2
# channel2.gas = "SiH4"
# channel2.flow_rate = "2"

# channel3 = SixChamberChannel(layer)
# channel3.number = 3
# channel3.gas = "SiH4"
# channel3.flow_rate = "3"

# six_chamber_deposition.layers.extend([layer, layer])

# for i in range(10):
#     six_chamber_deposition.submit(connection)
#     six_chamber_deposition.sample_name = None
