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
    def get_new_samples(self, number_of_samples, current_location, substrate=u"asahi-u", purpose=u"", tags=u"", group=u""):
        self.open("samples/add/")
        self.browser["number_of_samples"] = str(number_of_samples)
        self.browser["current_location"] = current_location
        self.browser["substrate"] = [substrate]
        self.browser["purpose"] = purpose
        self.browser["tags"] = tags
        if group:
            self.browser["group"] = [self.selection_options["group"][group]]
        self.browser["currently_responsible_person"] = \
            [self.selection_options["currently_responsible_person"][self.username]]
        return self.submit().split(",")
    def __del__(self):
        self.browser.open(self.root_url+"logout")

# class SixChamberDeposition(object):
#     def __init__(self, number, carrier, operator, timestamp=None):
#         self.number = number
#         self.carrier = carrier
#         self.operator = operator
#         self.timestamp = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         self.comments = u""

# class SixChamberLayer(object):
#     def __init__(self, number, chamber):
#         self.number, self.chamber = number, chamber

# def add_layer(deposition):
#     browser.open(root_url+"6-chamber_depositions/%s/edit/"%deposition)
#     browser.select_form(nr=0)
#     browser["structural-change-add-layers"] = "1"
#     browser.submit()
#     browser.select_form(nr=0)
#     browser["0-chamber"] = ["#4"]
#     browser.submit()


connection = ChantalConnection("bronger", "*******", "http://127.0.0.1:8000/")
print connection.get_new_samples(10, "Hall lab")
