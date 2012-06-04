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
import cPickle as pickle, re, codecs, os.path, datetime
import shared_utils
from chantal_remote import *
import chantal_remote

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

root_dir = "/home/bronger/temp/clustertools/"

depositions = {}

for row in ElementTree.parse(os.path.join(root_dir, "ct1_depos.xml")).getroot():
    deposition = {}
    for attribute in row:
        deposition[attribute.tag] = attribute.text
    deposition["layers"] = {}
    deposition["deposition_number"] = deposition["deposition_number"].upper()
    depositions[deposition["deposition_number"]] = deposition

for row in ElementTree.parse(os.path.join(root_dir, "ct1_layers.xml")).getroot():
    layer = {}
    for attribute in row:
        layer[attribute.tag] = attribute.text
    layer["deposition_number"] = layer["deposition_number"].upper()
    depositions[layer["deposition_number"]]["layers"][int(layer["layer_number"])] = layer

for row in ElementTree.parse(os.path.join(root_dir, "ct1_gases.xml")).getroot():
    channel = {}
    for attribute in row:
        channel[attribute.tag] = attribute.text
    channel["deposition_number"] = channel["deposition_number"].upper()
    channel["gas_and_dillution"] = channel["gas_and_dillution"].rstrip(" in").strip()
    layer = depositions[channel["deposition_number"]]["layers"][int(channel["layer_number"])]
    try:
        layer[channel["gas_and_dillution"]] = channel["flow_rate"]
    except KeyError:
        pass

for deposition_number in list(depositions):
    deposition = depositions[deposition_number]
    if deposition_number[2:3] != "C":
        del depositions[deposition_number]
    elif not deposition["layers"]:
        del depositions[deposition_number]
    else:
        for layer_number, layer in deposition["layers"].iteritems():
            if "chamber" not in layer:
                del depositions[deposition_number]
                break
            chamber_mapping = {1: 10, 2: 12, 3: 11, 4: 11, 5: 10, 6: 12}
            chamber = int(layer["chamber"])
            if chamber in chamber_mapping:
                layer["comments"] = (layer.get("comments", "") + 
                                     "\n“chamber” was erroneously set to “{0}”.".format(layer["chamber_name"])).lstrip("\n")
                chamber = chamber_mapping[chamber]
            if chamber not in range(10, 14):
                del depositions[deposition_number]
                break
            layer["chamber"] = chamber

# pickle.dump(depositions, open("/tmp/sct.pickle", "wb"), pickle.HIGHEST_PROTOCOL)

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
    "AD/AG": "a.dasgupta",
    "AD/JW": "a.dasgupta",
    "AD/YH": "a.dasgupta",
    "SK": "s.klein",
    "SK/YM": "s.klein",
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
    "SR": "s.reynolds",
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
    "JL": "j.lossen",
    "YM": "y.mai",
    "APV": "a.pollet.villard",
    "YH": "y.huang",
    "ML": "m.leotsakou",
    "TC": "t.chen",
    "FE": "f.einsele",
    "ÜD": "u.dagkaldiran",
    "KD": "k.ding",
    "GY": "g.yilmaz",
    "AS": "a.schmalen",
    "SA": "o.astakhov",
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
def normalize_quantity(quantity, coerce_unit=False, decimal_field=True):
    quantity = quantity.strip().replace(",", ".")
    if not quantity:
        return ""
    match = quantity_pattern.match(quantity)
    if match:
        if not match.group("value") or not match.group("value").strip():
            return ""
        if coerce_unit:
            value = float(match.group("value").strip())
            if match.group("unit") == "Torr":
                value *= 1.33322368421
            elif match.group("unit") == "mTorr":
                value *= 1.33322368421e-3
            else:
                assert match.group("unit").lower() == "mbar", match.group("unit")
            if decimal_field:
                quantity = list("{0:.5g}".format(value).partition("."))
                if "e" in quantity[2]:
                    assert value < 0.001
                    return None
                quantity[2] = quantity[2][:3]
                quantity = "".join(quantity).rstrip("0").rstrip(".")
            else:
                quantity = str(value)
        else:
            quantity = match.group("value").strip() + " " + match.group("unit")
        return quantity.replace("mBar", "mbar")
    if coerce_unit:
        return quantity
    print quantity + " could not be parsed as a quantity"
    return ""

# depositions = pickle.load(open("/tmp/sct.pickle", "rb"))

login(credentials["crawlers_login"], credentials["crawlers_password"], testserver=True)

already_available_deposition_numbers = OldClusterToolDeposition.get_already_available_deposition_numbers()

last_date = None
legacy_deposition_number_pattern = re.compile(r"\d\dC ?(?P<number>\d+)([*,]|FE)?$")
for deposition_number in sorted(depositions, reverse=True):
    raw_deposition = depositions[deposition_number]
    match = legacy_deposition_number_pattern.match(deposition_number)
    if not match:
        print "Ignored", deposition_number
        continue
    deposition_number = deposition_number[:3] + "-{0:03}".format(int(match.group("number")))
    if deposition_number in already_available_deposition_numbers:
        print deposition_number, "is already in the database"
        continue
    substrate = shared_utils.sanitize_for_markdown(raw_deposition.get("substrate", ""))
    comments = shared_utils.sanitize_for_markdown(raw_deposition.get("comments", ""))
    if "date" not in raw_deposition:
        print deposition_number, "doesn't have a date."
        continue
    raw_deposition["date"] = raw_deposition["date"][:10]
    if not deposition_number.startswith(raw_deposition["date"][2:4]):
        comments += "Deposition date was {0}.  \n".format(raw_deposition["date"])
        raw_deposition["date"] = "20{0}-12-31".format(deposition_number[:2])
    timestamp = datetime.datetime.strptime(raw_deposition["date"] + " 10:00:00", "%Y-%m-%d %H:%M:%S")
    sample = get_or_create_sample(deposition_number, substrate, timestamp, comments=comments, add_zno_warning=True)
    deposition = OldClusterToolDeposition()
    deposition.sample_ids = [sample]
    deposition.number = deposition_number
    deposition.timestamp = timestamp
    deposition.timestamp_inaccuracy = 3
    deposition.comments = comments
    try:
        deposition.operator = operators[raw_deposition.get("operator_initials", "JW")]
    except KeyError:
        print raw_deposition.get("operator_name")
        raise
    deposition.carrier = raw_deposition.get("carrier", "")
    for layer_number in sorted(raw_deposition["layers"]):
        raw_layer = raw_deposition["layers"][layer_number]
        if raw_layer["chamber"] == 13 and raw_layer.get("deposition_frequency") != "13.56":
            layer = OldClusterToolHotWireLayer(deposition)
            layer.comments = ""
            layer.substrate_wire_distance = raw_layer.get("substrate_electrode_distance", "")
            layer.filament_temperature = raw_layer.get("deposition_frequency", "")
            # if raw_layer.get(u"deposition_frequency_unit", u"°C") != u"°C":
            #     print deposition_number + u": Einheit der Filamenttemp. war " + raw_layer[u"deposition_frequency_unit"]
            layer.current = raw_layer.get("deposition_power", "")
            # if raw_layer.get(u"deposition_power_unit", u"A") != u"A":
            #     print deposition_number + u": Einheit des Drahtstroms war " + raw_layer[u"deposition_power_unit"]
            layer.voltage = None
            layer.wire_power = None
            layer.wire_material = "unknown"
        else:
            layer = OldClusterToolPECVDLayer(deposition)
            layer.comments = ""
            if raw_layer["chamber"] == 13:
                layer.chamber = "#1"
                layer.comments += "This layer was erroneously put into the hot-wire chamber.  \n"
            else:
                layer.chamber = {10: "#1", 11: "#2", 12: "#3"}[raw_layer["chamber"]]
            layer.substrate_electrode_distance = raw_layer.get("substrate_electrode_distance", "")
            layer.plasma_start_power = raw_layer.get("plasma_start_power", "")
            layer.plasma_start_with_shutter = raw_layer.get("plasma_start_with_carrier", "")
            layer.deposition_frequency = raw_layer.get("deposition_frequency", "")
            if layer.deposition_frequency and float(layer.deposition_frequency) >= 1000:
                layer.comments += "This layer had the plasma frequency “{0}”.  \n".format(layer.deposition_frequency)
                layer.deposition_frequency = None
            layer.deposition_power = raw_layer.get("deposition_power", "")
        layer.pressure = normalize_quantity(raw_layer.get("pressure", ""), coerce_unit=True)
        layer.time = raw_layer.get("time", "")[11:]
        layer.comments += shared_utils.sanitize_for_markdown(raw_layer.get("comments", ""))
        layer.transfer_in_chamber = raw_layer.get("transfer_in_chamber", "")
        layer.pre_heat = format_pre_heat_time(raw_layer.get("pre_heat", ""))
        layer.gas_pre_heat_gas = raw_layer.get("gas_pre_heat_gas", "")
        layer.gas_pre_heat_pressure = normalize_quantity(raw_layer.get("gas_pre_heat_pressure", ""), coerce_unit=True)
        layer.gas_pre_heat_time = raw_layer.get("gas_pre_heat_time", "")[11:]
        layer.heating_temperature = raw_layer.get("heating_temperature", "")
        layer.transfer_out_of_chamber = raw_layer.get("transfer_out_of_chamber", "")
        layer.base_pressure = normalize_quantity(raw_layer.get("base_pressure", ""), coerce_unit=True, decimal_field=False)
        layer.h2 = raw_layer.get("H2", "")
        layer.sih4 = raw_layer.get("SiH4", "")
        layer.mms = raw_layer.get("5% MMS in H2", "")
        layer.tmb = raw_layer.get("2,54% TMB in He") or raw_layer.get("1% TMB in He") or ""
        layer.co2 = raw_layer.get("CO2", "")
        layer.ph3 = raw_layer.get("5% PH3 in SiH4") or raw_layer.get("2% Ph3 in SiH4") or \
            raw_layer.get("10ppm Ph3 in H2") or ""
        layer.ch4 = raw_layer.get("CH4", "")
        layer.ar = raw_layer.get("Ar", "")
        invalid_keys = set(["2% Ph3 in SiH4", "1% TMB in He", "10ppm Ph3 in H2", "GeH4", "0% Si2H6", "5ppm B2H6 in He"]) & \
            set(raw_layer.keys())
        # if invalid_keys:
        #     print deposition_number, invalid_keys
    deposition.submit()
    chantal_remote.connection.open("change_my_samples", {"remove": sample})
    already_available_deposition_numbers.add(deposition_number)
