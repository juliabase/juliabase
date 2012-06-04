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
import cPickle as pickle
import codecs, re, os.path, itertools
import shared_utils


class Layer(object):
    def __init__(self):
        self.fields = {}


root = ElementTree.parse("/tmp/content.xml")

topline_styles = []
bottomline_styles = []
bold_styles = []
medium_styles = []

for style in root.getiterator("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}style"):
    property_ = style.find("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}table-cell-properties")
    if property_ is not None:
        if property_.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}border-top", "none") != "none":
            topline_styles.append(style.attrib["{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"])
        if property_.attrib.get(
            "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}border-bottom", "none") != "none":
            bottomline_styles.append(style.attrib["{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"])
    property_ = style.find("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}text-properties")
    if property_ is not None:
        if property_.attrib.get(
            "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}font-weight") == "bold":
            bold_styles.append(style.attrib["{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"])
        if property_.attrib.get(
            "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}font-weight") == "normal":
            medium_styles.append(style.attrib["{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"])


def mark_bold(text, bold, in_bold):
    if bold and not in_bold:
        stripped_text = text.lstrip()
        text = text[:len(text) - len(stripped_text)] + "__" + stripped_text
        in_bold = True
    elif not bold and in_bold:
        text += "__"
        in_bold = False
    return text, in_bold


def inner_text(root, in_comment, in_bold=False):
    if root.tag == "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}annotation":
        return "", in_bold
    current_text = root.text or ""
    if in_comment:
        if root.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}style-name") in bold_styles or \
                root.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name") in bold_styles:
            bold = True
        elif root.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}style-name") in medium_styles or \
                root.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name") in medium_styles:
            bold = False
        else:
            bold = in_bold
        current_text, in_bold = mark_bold(current_text, bold, in_bold)
    for element in list(root):
        new_text, in_bold = inner_text(element, in_comment, in_bold)
        current_text += new_text
        if in_comment:
            current_text, in_bold = mark_bold(current_text, bold, in_bold)
        current_text += element.tail or ""
    return current_text, in_bold


def text(root, in_comment):
    complete_text, in_bold = inner_text(root, in_comment)
    if in_comment and in_bold:
        complete_text += "__"
    return complete_text


class EmptyRowException(Exception):
    pass


layers = []
depositions = []

columns = ("number", "date", "layer_type", "station", "sih4", "h2", "__", "tmb", "ch4", "co2", "ph3", "power",
           "pressure", "temperature", "hf_frequency", "time", "dc_bias", "__", "__", "__", "__", "__", "__", "__", "__",
           "__", "__", "__", "__", "__", "__", "__", "__", "__", "__", "__", "electrode", "electrodes_distance",
           "comments")


for row in root.getiterator("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row"):
    try:
        current_column = 0
        current_layer = Layer()
        last_layer_of_deposition = False
        for cell in row.getiterator("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell"):
            if current_column >= len(columns):
                break
            current_layer.fields[columns[current_column]] = text(cell, columns[current_column]=="comments")
            if current_column == 0 and not current_layer.fields["number"]:
                raise EmptyRowException
            if current_column == 38:
                stylename = cell.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}style-name")
                if stylename in topline_styles and layers:
                    depositions.append(layers)
                    layers = []
                if stylename in bottomline_styles:
                    last_layer_of_deposition = True
            current_column += int(
                cell.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:table:1.0}number-columns-repeated", 1))
        layers.append(current_layer)
        if last_layer_of_deposition:
            depositions.append(layers)
            layers = []
    except EmptyRowException:
        pass

# pickle.dump(depositions, open("large_area_depositions.pickle", "wb"))

# import sys
# sys.exit()

# depositions = pickle.load(open("large_area_depositions.pickle", "rb"))

del depositions[:5]


def datum2date(datum):
    return datum[6:10] + "-" + datum[3:5] + "-" + datum[0:2]


number_of_outfiles = 1
outfiles = [codecs.open("la_import_{0}.py".format(i), "w", encoding="utf-8") for i in range(number_of_outfiles)]

for i, outfile in enumerate(outfiles):
    print>>outfile, """#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from chantal_remote import *

import ConfigParser, os.path
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))


login(credentials["crawlers_login"], credentials["crawlers_password"])

"""

last_date = None
legacy_deposition_number_pattern = re.compile(r"\d\dL-(?P<number>\d+)$")
for deposition, outfile in itertools.izip(depositions, itertools.cycle(outfiles)):
    deposition_number = deposition[-1].fields["number"]
    if not deposition_number:
        continue
    match = legacy_deposition_number_pattern.match(deposition_number)
    deposition_number = deposition_number[:4] + "{0:03}".format(int(match.group("number")))
    comments = "  \n".join(layer.fields["comments"] for layer in deposition)
    while comments[-4:] == "\n\n":
        comments = comments[:-2]
    while comments[:2] == "\n":
        comments = comments[2:]
    comments = shared_utils.python_escape(comments.replace("____", "").strip())
    date = datum2date(deposition[-1].fields["date"])
    if last_date is None or last_date != date:
        minute = 0
    else:
        minute += 1
    assert minute < 60
    last_date = date
    print>>outfile, """sample = get_or_create_sample("{deposition_number}", "",
                              datetime.datetime.strptime("{date} 10:{minute:02}:00", "%Y-%m-%d %H:%M:%S"),
                              comments=u"{comments}", add_zno_warning=True)

deposition = LargeAreaDeposition()
deposition.sample_ids = [sample]
deposition.number = u"{deposition_number}"
deposition.operator = "j.kirchhoff"
deposition.comments = u"{comments}"
deposition.timestamp_inaccuracy = 3
deposition.timestamp = u'{date} 10:{minute:02}:00'""".format(date=date, deposition_number=deposition_number,
                                                             comments=comments, minute=minute)
    for layer in deposition:
        print>>outfile, "\nlayer = LargeAreaLayer(deposition)"
        if "-" in layer.fields["sih4"]:
            layer.fields["sih4"], layer.fields["sih4_end"] = layer.fields["sih4"].replace(",", ".").split("-")
        if "-" in layer.fields["h2"]:
            layer.fields["h2"], layer.fields["h2_end"] = layer.fields["h2"].replace(",", ".").split("-")
        for key, value in layer.fields.iteritems():
            if key != "__" and key != "comments":
                if key == "date":
                    value = datum2date(value)
                if key in ("sih4", "h2", "tmb", "ch4", "co2", "ph3", "power",
                           "pressure", "temperature", "hf_frequency", "time", "dc_bias", "electrodes_distance"):
                    value = value.replace(",", ".")
                    if key == "dc_bias" and (value == "3...4" or value == "3-4"):
                        value = "3.5"
                    if key == "dc_bias" and value == "ca!!!":
                        value = ""
                    if value == "?":
                        value = "0"
                    if key in ("h2", "power") and not value:
                        value = "0"
                    if key == "time" and value == "ca. 10'":
                        value = "10"
                    if key == "time" and value == "?":
                        value = "0"
                if key == "number":
                    value = value[4:]
                if value:
                    print>>outfile, "layer.{0} = u\"{1}\"".format(key, shared_utils.python_escape(value))
    print>>outfile, """
deposition_number = deposition.submit()

"""

print>>outfile, "\n\nlogout()\n"
