#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mechanize import Browser
from elementtree.ElementTree import XML
import datetime

class ChantalConnection(object):
    def __init__(self, username, password, chantal_url="http://bob.ipv.kfa-juelich.de/chantal/"):
        self.root_url = chantal_url
        self.browser = Browser()
        self.browser.set_handle_robots(False)
        self.username = username
        self.selection_options = {}

        # Login
        self.browser.open(self.root_url+"login")
        self.browser.select_form(nr=0)
        self.browser["username"] = username
        self.browser["password"] = password
        self.browser.submit()
        # FixMe: Test whether login was successful
    def open(self, relative_url):
        response = self.browser.open(self.root_url+relative_url)
        self.selection_options.clear()
        tree = XML(response.read())
        for selection in tree.getiterator("{http://www.w3.org/1999/xhtml}select"):
            selection_name = selection.attrib["name"]
            current_selection = self.selection_options[selection_name] = {}
            for option in selection.getiterator("{http://www.w3.org/1999/xhtml}option"):
                current_selection[option.text] = option.attrib["value"]
        self.browser.select_form(nr=0)
    def submit(self, get_success_report=True):
        response = self.browser.submit()
        if get_success_report:
            for meta in XML(response.read()).getiterator("{http://www.w3.org/1999/xhtml}meta"):
                if meta.attrib["name"] == "success-report":
                    return meta.attrib["content"]
            for div in XML(response.read()).getiterator("{http://www.w3.org/1999/xhtml}div"):
                if div.attrib["class"] == "success-report":
                    return div.text
            raise Exception("Didn't find a success report")
    def set_form_data(self, form_dict):
        for key, value in form_dict.iteritems():
            if value:
                if isinstance(value, list):
                    self.browser[key] = [unicode(item) for item in value]
                else:
                    try:
                        self.browser[key] = unicode(value)
                    except TypeError, e:
                        if e.message != "ListControl, must set a sequence":
                            raise
                        self.browser[key] = [unicode(value)]
    def get_new_samples(self, number_of_samples, current_location, substrate=u"asahi-u", purpose=u"", tags=u"", group=u""):
        self.open("samples/add/")
        print self.browser.form.controls["purpose"].__dict__
        self.set_form_data({"number_of_samples": number_of_samples,
                            "current_location": current_location,
                            "substrate": substrate,
                            "purpose": purpose,
                            "tags": tags,
                            "group": self.selection_options["group"][group] if group else None,
                            "currently_responsible_person":
                                self.selection_options["currently_responsible_person"][self.username]})
        return []
        return self.submit().split(",")
    def __del__(self):
        self.browser.open(self.root_url+"logout")

class SixChamberDeposition(object):
    def __init__(self, sample_name=None):
        self.sample_name = sample_name
        self.number = self.carrier = self.operator = self.timestamp = self.comments = u""
        self.layers = []
    def submit(self, connection):
        if not self.sample_name:
            self.sample_name = connection.get_new_samples(1, u"unknown due to legacy data")
        connection.open("6-chamber depositions/add/")
        connection.browser["number"] = unicode(self.number)

class SixChamberLayer(object):
    def __init__(self, deposition):
        deposition.layers.append(self)
        self.number = self.chamber = self.chamber = self.pressure = self.time = \
            self.substrate_electrode_distance = self.comments = self.transfer_in_chamber = self.pre_heat = \
            self.gas_pre_heat_gas = self.gas_pre_heat_pressure = self.gas_pre_heat_time = self.heating_temperature = \
            self.transfer_out_of_chamber = self.plasma_start_power = self.plasma_start_with_carrier = \
            self.deposition_frequency = self.deposition_power = self.base_pressure = u""
        self.channels = []

class SixChamberChannel(object):
    def __init__(self, layer):
        layer.channels.append(self)
        self.number = self.gas = self.flow_rate = u""


connection = ChantalConnection("bronger", "*******", "http://127.0.0.1:8000/")
print connection.get_new_samples(10, "Hall lab")
