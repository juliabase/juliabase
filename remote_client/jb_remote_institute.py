#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

"""Library for communicating with JuliaBase through HTTP.  Typical usage is::

    from jb_remote import *
    login("r.miller", "mysecurepassword")
    new_samples(10, "PECVD lab")
    logout()

This module writes a log file.  On Windows, it is in the current directory.  On
Unix-like systems, it is in /tmp.
"""

from __future__ import absolute_import, unicode_literals

import re, logging, datetime, urllib
from jb_remote import *


settings.root_url = settings.testserver_root_url = "http://demo.juliabase.org/"


class ClusterToolDeposition(object):
    """Class representing Cluster Tool depositions.
    """

    def __init__(self, number=None):
        if number:
            data = connection.open("cluster_tool_depositions/{0}".format(number))
            self.sample_ids = data["sample IDs"]
            self.operator = data["operator"]
            self.timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            self.timestamp_inaccuracy = data["timestamp inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.carrier = data["carrier"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                if layer_data["layer type"] == "PECVD":
                    ClusterToolPECVDLayer(self, layer_data)
                elif layer_data["layer type"] == "hot-wire":
                    ClusterToolHotWireLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.number = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.carrier = None
            self.layers = []
            self.existing = False
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/C")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": False}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("cluster_tool_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("cluster_tool_depositions/add/", data)
                logging.info("Successfully added cluster tool deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/ClusterToolDeposition"))


class ClusterToolHotWireLayer(object):
    """Class representing Cluster Tool hot-wire layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.time = data["time"]
            self.comments = data["comments"]
            self.wire_material = data["wire material"]
            self.base_pressure = data["base pressure/mbar"]
            self.h2 = data["H2/sccm"]
            self.sih4 = data["SiH4/sccm"]
        else:
            self.time = self.comments = self.wire_material = self.base_pressure = self.h2 = self.sih4 = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "hot-wire",
                prefix + "time": self.time,
                prefix + "comments": self.comments,
                prefix + "wire_material": self.wire_material,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4}
        return data


class ClusterToolPECVDLayer(object):
    """Class representing Cluster Tool PECVD layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.time = data["time"]
            self.comments = data["comments"]
            self.plasma_start_with_shutter = data["plasma start with shutter"]
            self.deposition_power = data["deposition power/W"]
            self.h2 = data["H2/sccm"]
            self.sih4 = data["SiH4/sccm"]
        else:
            self.chamber = self.pressure = self.time = self.comments = self.plasma_start_with_shutter = \
                self.deposition_power = self.h2 = self.sih4 = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "layer_type": "PECVD",
                prefix + "chamber": self.chamber,
                prefix + "time": self.time,
                prefix + "comments": self.comments,
                prefix + "plasma_start_with_shutter": self.plasma_start_with_shutter,
                prefix + "deposition_power": self.deposition_power,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4}
        return data


def rename_after_deposition(deposition_number, new_names):
    """Rename samples after a deposition.  In the IEK-PV, it is custom to give
    samples the name of the deposition after the deposition.  This is realised
    here.

    :Parameters:
      `deposition_number`: the number of the deposition
      `new_names`: the new names of the samples.  The keys of this dictionary
        are the sample IDs.  The values are the new names.  Note that they must
        start with the deposition number.

    :type deposition_number: unicode
    :type new_samples: dict mapping int to unicode
    """
    data = {}
    for i, id_ in enumerate(new_names):
        data["{0}-sample".format(i)] = id_
        data["{0}-number_of_pieces".format(i)] = 1
        data["0-new_name"] = data["{0}_0-new_name".format(i)] = new_names[id_]
    connection.open("depositions/split_and_rename_samples/" + deposition_number, data)


class PDSMeasurement(object):
    """Class representing PDS measurements.
    """

    def __init__(self, number=None):
        """Class constructor.
        """
        if number:
            data = connection.open("pds_measurements/{0}".format(number))
            self.sample_id = data["sample IDs"][0]
            self.number = data["PDS number"]
            self.operator = data["operator"]
            self.timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            self.timestamp_inaccuracy = data["timestamp inaccuracy"]
            self.comments = data["comments"]
            self.apparatus = data["apparatus"]
            self.raw_datafile = data["raw data file"]
            self.existing = True
        else:
            self.sample_id = self.number = self.operator = self.timestamp = self.comments = self.apparatus = None
            self.timestamp_inaccuracy = 0
            self.raw_datafile = None
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"number": self.number,
                "apparatus": self.apparatus,
                "sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "raw_datafile": self.raw_datafile,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important
                }
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                connection.open("pds_measurements/{0}/edit/".format(self.number), data)
            else:
                return connection.open("pds_measurements/add/", data)

    @classmethod
    def get_already_available_pds_numbers(cls):
        """Returns the already available PDS numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available PDS numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/PDSMeasurement"))


class Substrate(object):
    """Class representing substrates in the database.
    """

    def __init__(self, initial_data=None):
        """Class constructor.  Note that in contrast to the processes, you
        currently can't retrieve an existing substrate from the database
        (except by retrieving its respective sample).
        """
        if initial_data:
            self.id, self.timestamp, self.timestamp_inaccuracy, self.operator, self.external_operator, self.material, \
                self.comments, self.sample_ids = \
                initial_data["ID"], \
                datetime.datetime.strptime(initial_data["timestamp"].partition(".")[0], "%Y-%m-%d %H:%M:%S"), \
                initial_data["timestamp inaccuracy"], initial_data["operator"], initial_data["external operator"], \
                initial_data["material"], initial_data["comments"], initial_data["sample IDs"]
        else:
            self.id = self.timestamp = self.operator = self.external_operator = self.material = self.comments = None
            self.timestamp_inaccuracy = 0
            self.sample_ids = []

    def submit(self):
        data = {"timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "material": self.material,
                "comments": self.comments,
                "operator": primary_keys["users"][self.operator],
                "external_operator": self.external_operator and primary_keys["external_operators"][self.external_operator],
                "sample_list": self.sample_ids}
        if self.id:
            data["edit_description-description"] = "automatic change by a non-interactive program"
            connection.open("substrates/{0}/edit/".format(self.id), data)
        else:
            return connection.open("substrates/add/", data)


class SampleNotFound(Exception):
    """Raised if a sample was not found in `get_sample`.  If you catch such an
    exception, you have to fill in the missing attributes of the sample and
    submit it.

    :ivar sample: a newly created `Sample` instance with only the name set, and
      not yet sumbitted to the database.

    :type sample: `Sample`
    """
    def __init__(self, sample):
        super(SampleNotFound, self).__init__()
        self.sample = sample

name_pattern = re.compile(r"\d\d[A-Z]-\d{{3,4}}([-A-Za-z_/][-A-Za-z_/0-9#()]*)?"
                          r"|(\d\d-[A-Z]{2}[A-Z0-9]{0,2}|[A-Z]{2}[A-Z0-9]{2})-[-A-Za-z_/0-9#()]+")
allowed_character_pattern = re.compile("[-A-Za-z_/0-9#()]")

def get_sample(sample_name):
    """Looks up a sample name in the database, and returns its ID.  (No full
    `Sample` instance is returned to spare ressources.  Mostly, only the ID is
    subsequently needed after all.)  You can only use this function if you are
    an administrator.  This function is used in crawlers and legacy importers.
    The sample is added to “My Samples”.

    If the sample name doesn't fit into the naming scheme, a legacy sample name
    accoring to ``{short_year}-LGCY-...`` is generated.

    :Parameters:
      - `sample_name`: the name of the sample

    :type sample_name: unicode

    :Return:
      the ID of the sample

    :rtype: int

    :Exceptions:
      - `SampleNotFound`: Raised if the sample was not found.  It contains a
        newly created sample and substrate for your convenience.  See the
        documentation of this exception class for more information.
    """

    if not name_pattern.match(sample_name):
        # Build a legacy name with the ``{short_year}-LGCY-`` prefix.
        allowed_sample_name_characters = []
        for character in sample_name:
            if allowed_character_pattern.match(character):
                allowed_sample_name_characters.append(character)
        sample_name = "{}-LGCY-{}".format(str(datetime.datetime.now())[2:], "".join(allowed_sample_name_characters)[:30])
    sample_id = connection.open("primary_keys?samples=" + urllib.quote_plus(sample_name))["samples"].get(sample_name)
    if sample_id is not None and not isinstance(sample_id, list):
        return sample_id
    else:
        new_sample = Sample()
        new_sample.name = sample_name
        raise SampleNotFound(new_sample)


class SolarsimulatorMeasurement(object):

    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("solarsimulator_measurements/{0}".format(process_id))
            self.process_id = process_id
            self.irradiance = data["irradiance"]
            self.temperature = data["temperature/degC"]
            self.sample_id = data["sample IDs"][0]
            self.operator = data["operator"]
            self.timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            self.timestamp_inaccuracy = data["timestamp inaccuracy"]
            self.comments = data["comments"]
            self.cells = {}
            for key, value in data.items():
                if key.startswith("cell position "):
                    cell = SolarsimulatorCellMeasurement(value)
                    self.cells[cell.position] = cell
            self.existing = True
        else:
            self.process_id = self.irradiance = self.temperature = self.sample_id = self.operator = self.timestamp = \
                self.timestamp_inaccuracy = self.comments = None
            self.cells = {}
            self.existing = False
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "irradiance": self.irradiance,
                "temperature": self.temperature,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, cell in enumerate(self.cells.values()):
            data.update(cell.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                query_string = "?only_single_cell_added=true" if only_single_cell_added else ""
                connection.open("solarsimulator_measurements/{0}/edit/".format(self.process_id) + query_string, data)
            else:
                return connection.open("solarsimulator_measurements/add/", data)


class SolarsimulatorCellMeasurement(object):

    def __init__(self, data={}):
        if data:
            self.position = data["cell position"]
            self.cell_index = data["cell index"]
            self.area = data["area/cm^2"]
            self.eta = data["efficiency/%"]
            self.p_max = data["maximum power point/mW"]
            self.ff = data["fill factor/%"]
            self.isc = data["short-circuit current density/(mA/cm^2)"]
            self.data_file = data["data file name"]
        else:
            self.position = self.cell_index = self.area = self.eta = self.p_max = self.ff = \
                self.isc = self.data_file = None

    def get_data(self, index):
        prefix = six.text_type(index) + "-"
        return {prefix + "position": self.position,
                prefix + "cell_index": self.cell_index,
                prefix + "area": self.area,
                prefix + "eta": self.eta,
                prefix + "p_max": self.p_max,
                prefix + "ff": self.ff,
                prefix + "isc": self.isc,
                prefix + "data_file": self.data_file}

    def __eq__(self, other):
        return self.cell_index == other.cell_index and self.data_file == other.data_file


class Structuring(object):
    def __init__(self):
        self.sample_id = None
        self.process_id = None
        self.operator = None
        self.timestamp = None
        self.timestamp_inaccuracy = None
        self.comments = None
        self.layout = None
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "process_id": self.process_id,
                "layout": self.layout,
                "comments": self.comments,
                "remove_from_my_samples": True,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.process_id:
                connection.open("structuring_process/{0}/edit/".format(self.process_id), data)
            else:
                return connection.open("structuring_process/add/", data)


class FiveChamberDeposition(object):
    """Class that represents 5-chamber depositions.
    """

    def __init__(self, number=None):
        """Class constructor.

        :Parameters:
          - `number`: if given, the instance represents an existing deposition
            of the database.  Note that this triggers an exception if the
            deposition number is not found in the database.

        :type number: unicode
        """
        if number:
            data = connection.open("5-chamber_depositions/{0}".format(number))
            self.sample_ids = data["sample IDs"]
            self.operator = data["operator"]
            self.timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            self.timestamp_inaccuracy = data["timestamp inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                FiveChamberLayer(self, layer_data)
            self.existing = True
        else:
            self.sample_ids = []
            self.operator = self.timestamp = None
            self.comments = ""
            self.timestamp_inaccuracy = 0
            self.layers = []
            self.existing = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the depositon to the database.

        :Return:
          the deposition number if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        if self.number is None:
            self.number = connection.open("next_deposition_number/S")
        data = {"number": self.number,
                "operator": primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "sample_list": self.sample_ids,
                "remove_from_my_samples": True,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("5-chamber_depositions/{0}/edit/".format(self.number), data)
            else:
                result = connection.open("5-chamber_depositions/add/", data)
                logging.info("Successfully added 5-chamber deposition {0}.".format(self.number))
        return result

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :Return:
          all already available deposition numbers

        :rtype: set of unicode
        """
        return set(connection.open("available_items/FiveChamberDeposition"))


class FiveChamberLayer(object):
    """Class representing a single 5-chamber layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.temperature_1 = data["T/degC (1)"]
            self.temperature_2 = data["T/degC (2)"]
            self.layer_type = data["layer type"]
            self.sih4 = data["SiH4/sccm"]
            self.h2 = data["H2/sccm"]
            self.silane_concentration = data["SC/%"]
            self.date = data["date"]
        else:
            self.chamber = self.temperature_1 = self.temperature_2 = self.layer_type = \
                self.sih4 = self.h2 = self.silane_concentration = self.date = None

    def get_data(self, layer_index):
        prefix = six.text_type(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "chamber": self.chamber,
                prefix + "temperature_1": self.temperature_1,
                prefix + "temperature_2": self.temperature_2,
                prefix + "date": self.date,
                prefix + "layer_type": self.layer_type,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2}
        return data
