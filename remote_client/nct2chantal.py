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
import cPickle as pickle, re, codecs, os.path, datetime, csv, socket
import shared_utils
from chantal_remote import *


path_root = "/home/bronger/temp/" if socket.gethostname() == "wilson" else "/tmp/"



class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)
    def __iter__(self):
        return self
    def next(self):
        return self.reader.next().encode("utf-8")

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """
    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwargs):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwargs)
    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]
    def __iter__(self):
        return self

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """
    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwargs):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwargs)
    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]
    def __iter__(self):
        return self


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
    "SM": "s.michard",
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
    "TC/SM": "t.chen",
    "FE": "f.einsele",
    "ÜD": "u.dagkaldiran",
    "KD": "k.ding",
    "GY": "g.yilmaz",
    "AS": "a.schmalen",
    "SA": "o.astakhov",
    "EM": "e.marins",
    "MW/AS": "m.warzecha",
    "MW/SM": "m.warzecha",
    "MW/EM": "m.warzecha",
    "MW/KB": "m.warzecha",
    "MW": "m.warzecha",
    "KB": "k.baumgartner",
    "KB/SM": "k.baumgartner",
    }


import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

depositions = {}

for row in ElementTree.parse(path_root + "clustertools/ct2_depos.xml").getroot():
    deposition = {}
    for attribute in row:
        deposition[attribute.tag] = attribute.text
    deposition["layers"] = {}
    deposition["deposition_number"] = deposition["deposition_number"].upper()
    depositions[deposition["deposition_number"]] = deposition

for row in ElementTree.parse(path_root + "clustertools/ct2_layers.xml").getroot():
    layer = {}
    for attribute in row:
        layer[attribute.tag] = attribute.text
    layer["deposition_number"] = layer["deposition_number"].upper()
    depositions[layer["deposition_number"]]["layers"][int(layer["layer_number"])] = layer

for row in ElementTree.parse(path_root + "clustertools/ct2_gases.xml").getroot():
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

legacy_deposition_number_pattern = re.compile(r"\d\d[OPQ]-?(?P<number>\d+)$")

for deposition_number in list(depositions):
    deposition = depositions.pop(deposition_number)
    match = legacy_deposition_number_pattern.match(deposition_number)
    if not match:
        print "Ignored", deposition_number
        continue
    deposition_number = deposition_number[:3] + "-{0:03}".format(int(match.group("number")))
    for layer_number, layer in deposition["layers"].iteritems():
        chamber = int(layer["chamber"])
        if chamber not in range(4, 10):
            print deposition_number, "hatte eine ungültige Kammer", chamber
            break
        layer["chamber"] = chamber
    if deposition_number not in ["10O-059", "11P-104", "09P-999"]:
        depositions[deposition_number] = deposition


sputter_deposition_number_pattern = re.compile(r"\d\d[PQ]-?(?P<number>\d{3,4})$")
sputter_runs = {}
columns = ("deposition_number", "target", "mode", "ar", "ar_o2", "o2", "n2", "pressure", "throttle", "thermoelement",
           "pyrometer", "t_s", "rotational_speed", "pre_heat_time", "power", "u_bias", "pre_sputter_time", "sputter_time",
           "ion_treatment_time", "date", "thickness", "r_square", "deposition_rate", "specific_resistance", "comments", "__")
for line in UnicodeReader(open(path_root + "clustertools/ct2_sputtern.csv", "rb"), delimiter=","):
    run = dict((label, cell.strip()) for label, cell in zip(columns, line))
    for fieldname in run:
        if fieldname in ["ar", "ar_o2", "o2", "n2", "pressure", "throttle", "thermoelement",
                         "pyrometer", "t_s", "rotational_speed", "pre_heat_time", "power", "u_bias", "pre_sputter_time",
                         "sputter_time", "ion_treatment_time", "thickness", "r_square", "deposition_rate",
                         "specific_resistance"]:
            run[fieldname] = run[fieldname].replace(",", ".")
        if fieldname in ["thermoelement", "pyrometer", "t_s"]:
            if run[fieldname].upper() == "RT":
                run[fieldname] = "21"
        if run[fieldname] == "-":
            run[fieldname] = ""
    match = sputter_deposition_number_pattern.match(run["deposition_number"])
    if match:
        run["deposition_number"] = run["deposition_number"][:3] + "-{0:03}".format(int(match.group("number")))
        sputter_runs[run["deposition_number"]] = run
    else:
        print "Ignored sputter deposition", run["deposition_number"]


def create_p_hot_wire_layer(raw_layer, deposition):
    layer = PHotWireLayer(deposition)
    layer.comments = ""
    layer.substrate_wire_distance = raw_layer.get("substrate_electrode_distance", "")
    layer.filament_temperature = raw_layer.get("deposition_frequency", "")
    layer.current = raw_layer.get("deposition_power", "")
    layer.voltage = None
    layer.wire_power = None
    layer.wire_material = "unknown"
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
    layer.base_pressure = normalize_quantity(raw_layer.get("base_pressure", ""), coerce_unit=True,
                                             decimal_field=False)
    layer.h2 = raw_layer.get("0% H2", "")
    layer.sih4 = raw_layer.get("0% SiH4", "")
    layer.mms = raw_layer.get("5% MMS in H2", "")
    layer.tmb = raw_layer.get("2,5% TMB in He") or raw_layer.get("1% TMB in He") or ""
    layer.ch4 = raw_layer.get("0% CH4", "")
    layer.ph3_sih4 = raw_layer.get("5% PH3 in SiH4") or raw_layer.get("2% Ph3 in SiH4") or \
        raw_layer.get("10ppm Ph3 in H2") or ""
    layer.ar = raw_layer.get("0% Ar", "")
    layer.tmal = ""
    return layer


def create_sputter_layer(deposition, sputter_data, raw_layer=None):
    layer = NewClusterToolSputterLayer(deposition)
    if deposition.number in ["09Q-001", "10P-331"]:
        sputter_data["target"] += " + Ion"
    layer.comments = raw_layer.get("comments", "") if raw_layer is not None else ""
    if sputter_data["comments"]:
        layer.comments += "\n\n" + sputter_data["comments"]
    if ("RF" in sputter_data["mode"] or "RF" in sputter_data["power"]) and "ion" not in sputter_data["target"].lower():
        layer.slots[1].mode = "RF"
    if "DC" in sputter_data["mode"] or "DC" in sputter_data["power"]:
        layer.slots[2].mode = "DC"
    if "ion" in sputter_data["target"].lower():
        layer.slots[3].mode = "RF"
    targets = [target.strip() for target in sputter_data["target"].split("+")]
    assert len(targets) <= 3
    target_mapping = {"ZnO:Ga (1%)": "ZnO:Ga 1%", "ZnGaO (1%)": "ZnO:Ga 1%", "ZnMgO (50%)": "ZnMgO 50%",
                      "ZnGaO (2%)": "ZnO:Ga 2%", "ZnMgO(50%)": "ZnMgO 50%", "ZnO:Ga": "ZnO:Ga 2%",
                      "ZnO:Ga (2%)": "ZnO:Ga 2%", "ZnMgO": "ZnMgO 50%", "ZnGaO": "ZnO:Ga 2%", "ZnO": "ZnO (i)",
                      "ZnGaO(2%)": "ZnO:Ga 2%", "ZnO(i)": "ZnO (i)", "ZnO (0,5%)": "ZnO:Al 0.5%", "ion": "Ion"}
    targets = [target_mapping.get(target, target) for target in targets]
    if layer.slots[2].mode:
        layer.slots[2].target = [target for target in targets if ":" in target or target == "Ag"][0]
        dc_target_index = targets.index(layer.slots[2].target)
        del targets[dc_target_index]
    if layer.slots[3].mode:
        layer.slots[3].target = "Ion"
        ion_target_index = targets.index("Ion")
        del targets[ion_target_index]
    if targets:
        layer.slots[1].target = targets[0]
    layer.base_pressure = None
    layer.working_pressure = sputter_data["pressure"]
    layer.valve = sputter_data["throttle"]
    layer.set_temperature = None
    layer.thermocouple = sputter_data["thermoelement"]
    layer.ts = sputter_data["t_s"]
    layer.pyrometer = sputter_data["pyrometer"]
    layer.slots[1].power, layer.slots[1].power_end = get_multifield("power", "RF", sputter_data)
    layer.slots[2].power, layer.slots[2].power_end = get_multifield("power", "DC", sputter_data)
    layer.slots[3].power, layer.slots[3].power_end = get_multifield("power", "Ion", sputter_data)
    layer.slots[2].voltage, layer.slots[2].voltage_end = get_multifield("u_bias", "DC", sputter_data)
    layer.slots[1].u_bias, layer.slots[1].u_bias_end = get_multifield("u_bias", "RF", sputter_data)
    layer.slots[3].u_bias, layer.slots[3].u_bias_end = get_multifield("u_bias", "Ion", sputter_data)
    layer.ar = sputter_data["ar"]
    layer.o2 = sputter_data["o2"]
    layer.ar_o2 = sputter_data["ar_o2"]
    layer.pre_heat = sputter_data["pre_heat_time"]
    layer.pre_sputter_time = {"20 s": "0.33", "-": ""}.get(sputter_data["pre_sputter_time"],
                                                           sputter_data["pre_sputter_time"])
    sputter_time = {"02:30": "2.5"}.get(sputter_data["sputter_time"], sputter_data["sputter_time"])
    if layer.slots[1].mode:
        layer.slots[1].time = sputter_time
    if layer.slots[2].mode:
        layer.slots[2].time = sputter_time
    layer.slots[3].time = {"30 s": "0.5", "60min": "60", "03:18": "3.3"}.get(sputter_data["ion_treatment_time"],
                                                                             sputter_data["ion_treatment_time"])
    layer.large_shutter = None
    layer.small_shutter = None
    layer.rotational_speed = sputter_data["rotational_speed"]
    layer.loading_chamber = None


def get_multifield(fieldname, mode, sputter_data):
    field_value = {"100W": "100"}.get(sputter_data[fieldname], sputter_data[fieldname])
    if "ion" in sputter_data["target"].lower():
        if mode == "Ion":
            mode = "RF"
        elif mode == "RF":
            return None, None
    else:
        if mode == "Ion":
            return None, None
    match = re.search(r"(?P<value>\d+) ?" + mode, field_value, re.IGNORECASE)
    if match:
        return match.group("value"), None
    if sputter_data["mode"] == mode:
        return field_value.split("/") if "/" in field_value else (field_value, None)
    return None, None


def create_characterization_process(sputter_data, deposition):
    r_square = sputter_data["r_square"]
    thickness = sputter_data["thickness"]
    if r_square != "" or thickness != "":
        sputter_characterization = SputterCharacterization()
        sputter_characterization.sample_id = deposition.sample_ids[0]
        sputter_characterization.operator = "m.warzecha"
        sputter_characterization.timestamp = deposition.timestamp + datetime.timedelta(seconds=1)
        sputter_characterization.timestamp_inaccuracy = 3
        sputter_characterization.comments = "This characterisation was automatically imported."
        if r_square == ">4500":
            r_square = "4500"
            sputter_characterization.comments += "\n\n$R_\square$ was “>4500”."
        sputter_characterization.new_cluster_tool_deposition = deposition.number
        sputter_characterization.r_square = r_square
        if thickness:
            sputter_characterization.thickness = int(round(float(thickness)))
        sputter_characterization.submit()


login(credentials["crawlers_login"], credentials["crawlers_password"], testserver=True)

already_available_deposition_numbers = NewClusterToolDeposition.get_already_available_deposition_numbers().union(
    PHotWireDeposition.get_already_available_deposition_numbers())

last_date = None
p_hot_wire_number_pattern = re.compile(r"\d\do-?(?P<number>\d{3,4})", re.IGNORECASE)
for deposition_number in sorted(depositions, reverse=True):
    raw_deposition = depositions[deposition_number]
    if deposition_number in already_available_deposition_numbers:
        print deposition_number, "is already in the database"
        continue
    if "date" not in raw_deposition:
        print deposition_number, "doesn't have a date."
        continue
    comments = raw_deposition.get("comments", "")
    raw_deposition["date"] = raw_deposition["date"][:10]
    if not deposition_number.startswith(raw_deposition["date"][2:4]):
        comments += "Deposition date was {0}.  \n".format(raw_deposition["date"])
        raw_deposition["date"] = "20{0}-12-31".format(deposition_number[:2])
    substrate = raw_deposition.get("substrate", "")
    timestamp = datetime.datetime.strptime(raw_deposition["date"] + " 10:00:00", "%Y-%m-%d %H:%M:%S")
    sample = get_or_create_sample(deposition_number, substrate, timestamp, comments=comments, add_zno_warning=True)
    substrate = shared_utils.sanitize_for_markdown(substrate)
    comments = shared_utils.sanitize_for_markdown(comments)
    deposition = NewClusterToolDeposition()
    deposition.sample_ids = [sample]
    deposition.number = deposition_number
    deposition.timestamp = timestamp
    deposition.timestamp_inaccuracy = 3
    deposition.comments = comments
    try:
        deposition.operator = operators[raw_deposition.get("operator_initials", "AS")]
    except KeyError:
        try:
            deposition.operator = operators[raw_deposition.get("operator_initials", "AS").partition("/")[0]]
        except KeyError:
            print raw_deposition.get("operator_name")
            raise
    deposition.carrier = raw_deposition.get("carrier", "")
    p_hot_wire_layer = None
    for layer_number in sorted(raw_deposition["layers"]):
        raw_layer = raw_deposition["layers"][layer_number]
        if 4 <= raw_layer["chamber"] <= 7:
            # HW/PECVD new cluster tool
            if raw_layer["chamber"] == 7 and raw_layer.get("deposition_frequency") != "13.56":
                layer = NewClusterToolHotWireLayer(deposition)
                layer.comments = ""
                layer.substrate_wire_distance = raw_layer.get("substrate_electrode_distance", "")
                layer.filament_temperature = raw_layer.get("deposition_frequency", "")
                layer.current = raw_layer.get("deposition_power", "")
                layer.voltage = None
                layer.wire_power = None
                layer.wire_material = "unknown"
            else:
                layer = NewClusterToolPECVDLayer(deposition)
                layer.comments = ""
                if raw_layer["chamber"] == 7:
                    layer.chamber = "#1"
                    layer.comments += "This layer was erroneously put into the hot-wire chamber.  \n"
                else:
                    layer.chamber = {4: "#1", 5: "#2", 6: "#3"}[raw_layer["chamber"]]
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
            layer.base_pressure = normalize_quantity(raw_layer.get("base_pressure", ""), coerce_unit=True,
                                                     decimal_field=False)
            layer.h2 = raw_layer.get("0% H2", "")
            layer.sih4 = raw_layer.get("0% SiH4", "")
            layer.tmb = raw_layer.get("2,5% TMB in He") or raw_layer.get("1% TMB in He") or ""
            layer.co2 = raw_layer.get("0% CO2", "")
            layer.ph3 = raw_layer.get("5% PH3 in SiH4") or raw_layer.get("2% Ph3 in SiH4") or \
                raw_layer.get("10ppm Ph3 in H2") or ""
            layer.ch4 = raw_layer.get("0% CH4", "")
            layer.ar = raw_layer.get("0% Ar", "")
            layer.geh4 = raw_layer.get("GeH4", "")
            layer.b2h6 = raw_layer.get("5ppm B2H6 in He", "")
            layer.sih4_29 = ""
        elif raw_layer["chamber"] == 9:
            assert not p_hot_wire_layer
            p_hot_wire_layer = (raw_layer, layer_number)
        else:
            assert raw_layer["chamber"] == 8
            # Sputter layer
            try:
                sputter_data = sputter_runs[deposition_number]
            except KeyError:
                deposition.comments += "\n\nThere was also a sputter layer for which no sputter data was found."
                print deposition_number, "wurde nicht in den Sputterdaten gefunden.  Layer ignoriert."
                continue
            create_sputter_layer(deposition, sputter_data, raw_layer)
    if p_hot_wire_layer:
        raw_layer, layer_number = p_hot_wire_layer
        p_hot_wire_deposition = PHotWireDeposition()
        p_hot_wire_deposition.sample_ids = [sample]
        if layer_number == 1:
            p_hot_wire_deposition.timestamp = timestamp - datetime.timedelta(seconds=1)
        elif layer_number == len(raw_deposition["layers"]):
            p_hot_wire_deposition.timestamp = timestamp + datetime.timedelta(seconds=1)
        else:
            raise Exception("p-hot-wire layer must be the first or last layer of the deposition {0}".format(
                    deposition_number))
        p_hot_wire_deposition.timestamp_inaccuracy = 3
        p_hot_wire_deposition.comments = comments
        layer = create_p_hot_wire_layer(raw_layer, p_hot_wire_deposition)
        match = p_hot_wire_number_pattern.search(raw_layer.get("comments", ""))
        if match:
            quirky_number = match.group(0)
            p_hot_wire_deposition.number = quirky_number[:2] + "O-" + match.group("number")
            if p_hot_wire_deposition.number in already_available_deposition_numbers:
                print deposition_number, "is already in the database"
                continue
            p_hot_wire_deposition.submit()
        else:
            print "Could not find O-deposition number in p-hot-wire layer", deposition_number
    if deposition.layers:
        deposition.submit()
        if any(isinstance(layer, NewClusterToolSputterLayer) for layer in deposition.layers):
            create_characterization_process(sputter_data, deposition)
        already_available_deposition_numbers.add(deposition_number)
    else:
        print deposition.number, "has no layers."
#    Sample(id_=sample).remove_from_my_samples()


# Now for the sputter-only cluster-tool-II depositions
for deposition_number in sorted(sputter_runs, reverse=True):
    if deposition_number[2] == "Q":
        if deposition_number in already_available_deposition_numbers:
            print deposition_number, "is already in the database"
            continue
        sputter_run = sputter_runs[deposition_number]
        comments = shared_utils.sanitize_for_markdown(sputter_run["comments"])
        if not deposition_number.startswith(sputter_run["date"][8:10]):
            comments += "\n\nDeposition date was {0}.  \n".format(sputter_run["date"])
            sputter_run["date"] = "31.12.20{0}".format(deposition_number[:2])
        timestamp = datetime.datetime.strptime(sputter_run["date"] + " 10:00:00", "%d.%m.%Y %H:%M:%S")
        sample = get_or_create_sample(deposition_number, "", timestamp, comments=comments)
        deposition = NewClusterToolDeposition()
        deposition.sample_ids = [sample]
        deposition.number = deposition_number
        deposition.timestamp = timestamp
        deposition.timestamp_inaccuracy = 3
        deposition.comments = comments
        create_sputter_layer(deposition, sputter_run)
        deposition.submit()
        create_characterization_process(sputter_run, deposition)

logout()
