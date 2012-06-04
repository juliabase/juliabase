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
import xml.etree.cElementTree as ElementTree
import cPickle as pickle, re, codecs, os.path
import shared_utils

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

# depositions = {}

# for row in ElementTree.parse("/home/bronger/temp/chantal_depositions.xml").getroot():
#     deposition = {}
#     for attribute in row:
#         deposition[attribute.tag] = attribute.text
#     deposition["layers"] = {}
#     deposition["deposition_number"] = deposition["deposition_number"].upper()
#     depositions[deposition["deposition_number"]] = deposition

# for row in ElementTree.parse("/home/bronger/temp/chantal_layers.xml").getroot():
#     layer = {}
#     for attribute in row:
#         layer[attribute.tag] = attribute.text
#     layer["channels"] = []
#     layer["deposition_number"] = layer["deposition_number"].upper()
#     depositions[layer["deposition_number"]]["layers"][int(layer["layer_number"])] = layer

# for row in ElementTree.parse("/home/bronger/temp/chantal_channels.xml").getroot():
#     channel = {}
#     for attribute in row:
#         channel[attribute.tag] = attribute.text
#     channel["deposition_number"] = channel["deposition_number"].upper()
#     depositions[channel["deposition_number"]]["layers"][int(channel["layer_number"])]["channels"].append(channel)

# for deposition_number in list(depositions):
#     deposition = depositions[deposition_number]
#     if deposition_number[2:3] != "B":
# #        print deposition_number, "hasn't a \"B\" in the deposition number"
#         del depositions[deposition_number]
#     elif not deposition["layers"]:
#         print deposition_number, "has no layers"
#         del depositions[deposition_number]
#     else:
#         for layer_number in deposition["layers"]:
#             layer = deposition["layers"][layer_number]
#             if "chamber" not in layer:
#                 print deposition_number, "has layer without chamber"
#                 del depositions[deposition_number]
#                 break
#             elif int(layer["chamber"]) not in range(1, 7):
#                 print deposition_number, "has layer with invalid chamber"
#                 del depositions[deposition_number]
#                 break

# pickle.dump(depositions, open("6k.pickle", "wb"))

# import sys
# sys.exit()

operators = {
    "AL": "a.lambertz",
    "JW": "j.wolff",
    "OV": "o.vetterl",
    "DL": "d.lundszien",
    "FF": "f.finger",
    "CM": "c.malten",
    "AD/AL": "a.dasgupta",
    "MK": "m.krause",
    "JM": "j.mueller",
    "AD": "a.dasgupta",
    "SK": "s.klein",
    "RS": "r.hollingsworth",
    "JW/DL": "j.wolff",
    "AG": "a.gross",
    "CR": "ch.ross",
    "JW/SK": "j.wolff",
    "SM": "s.michel",
    "JT": "j.tapati",
    "EB": "e.bunte",
    "LBN": "l.neto",
    "JK": "j.kirchhoff",
    "TD": "th.dylla",
    "YF": "y.feng",
    "OA": "o.astakhov",
    "SR": "s.raynolds",
    "AD/MZ": "a.dasgupta",
    "CD": "ch.das",
    "TM": "th.melle",
    "VS": "v.smirnov",
    "MS": "m.scholz",
    "TG": "th.grundler",
    "RvA": "r.van.aubel",
    "LX": "l.xiao",
    "SAM": "s.moll",
    "WB": "w.boettler",
    "BG": "b.grootoonk",
    }


hours_pattern = re.compile(r"(?P<hours>\d+)\s*h$")
minutes_pattern = re.compile(r"(?P<minutes>\d+)\s*min$")
def format_pre_heat_time(time):
    if not time:
        return ""
    if time in ["o.N.", "o.W."]:
        return ""
    if time == "kein pre heat":
        return "00:00:00"
    match = hours_pattern.match(time)
    if match:
        return "{0:02}:00:00".format(int(match.group("hours")))
    match = minutes_pattern.match(time)
    if match:
        minutes = int(match.group("minutes"))
        assert minutes < 60
        return "00:{0:02}:00".format(minutes)
    print time, "could not be parsed as a pre-heat time"


quantity_pattern = re.compile(r"(?P<value>[-+0-9.,eE]+)?\s*(?P<unit>(Torr)|(mBar)|(mTorr)|(hPa))$")
def normalize_quantity(quantity, base_pressure=False):
    quantity = quantity.strip().replace(",", ".")
    if not quantity:
        return ""
    match = quantity_pattern.match(quantity)
    if match:
        if not match.group("value") or not match.group("value").strip():
            return ""
        quantity = match.group("value").strip() + (" " + match.group("unit") if not base_pressure else "")
        return quantity.replace("mBar", "mbar")
    if base_pressure:
        return quantity
    print quantity + " could not be parsed as a quantity"
    return ""

gas_and_dilution = {0: None, 1: "SiH4", 2: "H2", 3: "PH3+SiH4", 4: "TMB", 5: "B2H6", 6: "CH4", 7: "CO2", 9: "GeH4", 10: "Ar",
                    11: "Si2H6", 12: "PH3_10ppm", 14: "PH3_5pc"}

depositions = pickle.load(open("6k.pickle", "rb"))

chambers = set()
outfile = codecs.open("6k_import.py", "w", "utf-8")
print>>outfile, """#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal_remote import *
import datetime, os.path

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

login(credentials["crawlers_login"], credentials["crawlers_password"])
"""
last_date = None
legacy_deposition_number_pattern = re.compile(r"\d\dB(?P<number>\d+)$")
for deposition_number in sorted(depositions):
    if deposition_number in ["97B091", "10B0100"]:
        print "Ignored", deposition_number
        continue
    elif deposition_number == "00B496":
        depositions[deposition_number]["date"] = "2000-11-15"
    elif deposition_number == "01B202":
        depositions[deposition_number]["date"] = "2001-03-23"
    elif deposition_number == "04B003":
        depositions[deposition_number]["date"] = "2004-02-08"
    elif deposition_number == "06B283":
        depositions[deposition_number]["date"] = "2006-12-31"
    deposition = depositions[deposition_number]
    match = legacy_deposition_number_pattern.match(deposition_number)
    if not match:
        print "Ignored", deposition_number
        continue
    deposition_number = deposition_number[:3] + "-{0:03}".format(int(match.group("number")))
    substrate = shared_utils.python_escape(shared_utils.sanitize_for_markdown(deposition.get("substrate", "")))
    comments = shared_utils.python_escape(shared_utils.sanitize_for_markdown(deposition.get("comments", "")))
    print>>outfile, """
sample = get_or_create_sample(u"{deposition_number}", u"{substrate}",
                              datetime.datetime.strptime("{timestamp} 10:00:00", "%Y-%m-%d %H:%M:%S"),
                              comments=u"{comments}",
                              add_zno_warning=True)

deposition = SixChamberDeposition()
deposition.sample_ids = [sample]
deposition.number = u"{deposition_number}"
deposition.carrier = u"{carrier}"
deposition.operator = u"{operator}"
deposition.comments = u"{comments}"
deposition.timestamp_inaccuracy = 3
deposition.timestamp = u'{timestamp} 10:00:00'
""".format(deposition_number=deposition_number,
           comments=comments,
           timestamp=deposition["date"][:10],
           carrier=deposition.get("carrier", ""),
           substrate=substrate,
           operator=operators[deposition.get("operator_initials", "AL")])
    operator_username = operators[deposition.get("operator_initials", "AL")]
    for i, layer_number in enumerate(sorted(deposition["layers"])):
        layer = deposition["layers"][layer_number]
        print>>outfile, """layer = SixChamberLayer(deposition)
layer.number = {number}
layer.chamber = "#{chamber}"
layer.pressure = "{pressure}"
layer.time = "{time}"
layer.substrate_electrode_distance = "{substrate_electrode_distance}"
layer.comments = u"{comments}"
layer.transfer_in_chamber = "{transfer_in_chamber}"
layer.pre_heat = "{pre_heat}"
layer.gas_pre_heat_gas = "{gas_pre_heat_gas}"
layer.gas_pre_heat_pressure = "{gas_pre_heat_pressure}"
layer.gas_pre_heat_time = "{gas_pre_heat_time}"
layer.heating_temperature = "{heating_temperature}"
layer.transfer_out_of_chamber = "{transfer_out_of_chamber}"
layer.plasma_start_power = "{plasma_start_power}"
layer.plasma_start_with_carrier = {plasma_start_with_carrier}
layer.deposition_frequency = "{deposition_frequency}"
layer.deposition_power = "{deposition_power}"
layer.base_pressure = "{base_pressure}"
""".format(number=i + 1, chamber=layer.get("chamber", "1"), pressure=normalize_quantity(layer.get("pressure")),
           time=layer.get("time", "")[11:],
           substrate_electrode_distance=layer.get("substrate_electrode_distance", ""),
           comments=shared_utils.sanitize_for_markdown(layer.get("comments", "")).\
               replace("\"", "\\\"").replace("\n-", "\n\\-").replace("\n", "\\n"),
           transfer_in_chamber=layer.get("transfer_in_chamber", ""),
           pre_heat=format_pre_heat_time(layer.get("pre_heat_time")),
           gas_pre_heat_gas="Ar" if layer.get("gas_pre_heat_pressure") or layer.get("gas_pre_heat_time") else "",
           gas_pre_heat_pressure=normalize_quantity(layer.get("gas_pre_heat_pressure")),
           gas_pre_heat_time=layer.get("gas_pre_heat_time", "")[11:],
           heating_temperature=layer.get("heating_temperature", ""),
           transfer_out_of_chamber=layer.get("transfer_out_of_chamber", ""),
           plasma_start_power=layer.get("plasma_start_power", ""),
           plasma_start_with_carrier=layer.get("plasma_start_with_carrier", "0") != "0",
           deposition_frequency=layer.get("deposition_frequency", ""),
           deposition_power=layer.get("deposition_power", ""),
           base_pressure=normalize_quantity(layer.get("base_pressure"), base_pressure=True))
        for channel in sorted(layer["channels"], key=lambda x: x["channel_number"]):
            try:
                gas_number = int(channel["gas_and_dillution"])
            except KeyError:
                print "Non-existing gas in channel {0} for deposition {1}.".format(channel["channel_number"],
                                                                                   deposition_number)
            else:
                try:
                    gas = gas_and_dilution[gas_number]
                except KeyError:
                    print "Invalid gas #{0} in channel {1} for deposition {2}.".format(
                        gas_number, channel["channel_number"], deposition_number)
                    raise
                else:
                    if gas:
                        print>>outfile, """channel = SixChamberChannel(layer)
channel.number = {number}
channel.gas = "{gas}"
channel.flow_rate = "{flow_rate}"
""".format(number=channel["channel_number"], gas=gas, flow_rate=channel.get("flow_rate", "0"))
                    else:
                        print deposition_number, "has empty gas field"


    print>>outfile, """
deposition_number = deposition.submit()

"""

print>>outfile, "\n\nlogout()\n"
