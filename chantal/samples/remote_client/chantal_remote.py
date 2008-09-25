#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, urllib2, cookielib, pickle, logging
from elementtree.ElementTree import XML
import datetime

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='chantal_remote.log',
                    filemode='w')

__all__ = ["login", "logout", "new_samples"]

def quote_header(value):
    return unicode(value).encode("utf-8")

class ChantalConnection(object):
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
    opener.addheaders = [("User-agent", "Chantal-Remote/0.1")]
    def __init__(self, chantal_url="http://bob.ipv.kfa-juelich.de/chantal/"):
        self.root_url = chantal_url
        self.username = None
        self.primary_keys = None
    def open(self, relative_url, data=None):
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
        is_pickled = response.info()["Content-Type"].startswith("text/x-python-pickle")
        if is_pickled:
            return pickle.load(response)
        else:
            logger.error("Resonse was not in pickle format.  Probably failed validation.")
            text = response.read()
            logfile = open("chantal_remote.html", "wb")
            logfile.write(text)
            logfile.close()
            raise Exception("Response was not in pickle format!")
    def login(self, username, password):
        self.username = username
        if not self.open("login_remote_client", {"username": username, "password": password}):
            logger.error("Login failed.")
            raise Exception("Login failed")
        # FixMe: Test whether login was successful
        self.primary_keys = pickle.load(self.opener.open(self.root_url+"primary_keys?groups=*&users=*"))
    def logout(self):
        if not self.open("logout_remote_client"):
            logger.error("Logout failed.")
            raise Exception("Logout failed")

connection = ChantalConnection()

def login(username, password):
    connection.login(username, password)
    logger.info("Successfully logged-in as %s." % username)

def logout():
    connection.logout()
    logger.info("Successfully logged-out.")

def new_samples(number_of_samples, current_location, substrate=u"asahi-u", timestamp=None, purpose=None, tags=None,
                group=None):
    samples = connection.open("samples/add/",
                              {"number_of_samples": number_of_samples,
                               "current_location": current_location,
                               "timestamp": timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               "substrate": substrate,
                               "purpose": purpose,
                               "tags": tags,
                               "group": connection.primary_keys["groups"].get(group),
                               "currently_responsible_person":
                                   connection.primary_keys["users"][connection.username]})
    logger.info("Successfully created %d samples with the ids %s." % (len(samples), ",".join(str(id_) for id_ in samples)))
    return samples

class SixChamberDeposition(object):
    def __init__(self, sample_ids):
        self.sample_ids = sample_ids
        self.number = self.carrier = self.operator = self.timestamp = self.comments = None
        self.layers = []
    def submit(self):
        # FixMe: Assure that sample is in MySamples
        date, time = self.timestamp.split(" ")
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = pickle.load(self.opener.open(self.root_url+"next_deposition_number/B"))
        data = {"number": self.number,
                "carrier": self.carrier,
                "operator": connection.primary_keys["users"][self.operator],
                "timestamp_0": date,
                "timestamp_1": time,
                "comments": self.comments,
                "sample_list": self.sample_ids}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        result = connection.open("6-chamber_depositions/add/", data)
        logger.info("Successfully added 6-chamber deposition %s." % )
        return result

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
    def get_data(self, layer_index):
        prefix = unicode(layer_index) + "-"
        data = {prefix+"number": layer_index + 1,
                prefix+"chamber": self.chamber,
                prefix+"pressure": self.pressure,
                prefix+"time": self.time,
                prefix+"substrate_electrode_distance": self.substrate_electrode_distance,
                prefix+"comments": self.comments,
                prefix+"transfer_in_chamber": self.transfer_in_chamber,
                prefix+"pre_heat": self.pre_heat,
                prefix+"gas_pre_heat_gas": self.gas_pre_heat_gas,
                prefix+"gas_pre_heat_pressure": self.gas_pre_heat_pressure,
                prefix+"gas_pre_heat_time": self.gas_pre_heat_time,
                prefix+"heating_temperature": self.heating_temperature,
                prefix+"transfer_out_of_chamber": self.transfer_out_of_chamber,
                prefix+"plasma_start_power": self.plasma_start_power,
                prefix+"plasma_start_with_carrier": self.plasma_start_with_carrier,
                prefix+"deposition_frequency": self.deposition_frequency,
                prefix+"deposition_power": self.deposition_power,
                prefix+"base_pressure": self.base_pressure}
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
        return {prefix+"number": self.number, prefix+"gas": self.gas, prefix+"flow_rate": self.flow_rate}

connection = ChantalConnection("bronger", "*******", "http://127.0.0.1:8000/")
