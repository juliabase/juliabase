# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

"""Library for communicating with JuliaBase through HTTP.  Typical usage is::

    from jb_remote_institute import *
    setup_logging("console")
    login("r.miller", "mysecurepassword")
    new_sample = Sample()
    new_sample.name = "14-RM-1"
    new_sample.current_location = "PECVD lab"
    logout()

This module writes a log file.  If the directory :file:`/var/lib/crawlers`
exists, it is written there.  Otherwise, it is written to the current
directory.  The directory is configurable by the environment variable
``CRAWLERS_DATA_DIR``.

Note that I don't use :py:func:`jb_remote.common.double_urlquote` here because
I *know* that my deposition and other process IDs don't contain dangerous
characters.
"""

import re, logging, datetime, os, urllib
from jb_remote import *


settings.ROOT_URL = settings.TESTSERVER_ROOT_URL = os.environ.get("JULIABASE_SERVER_URL", "http://localhost/")


class ClusterToolDeposition:
    """Class representing Cluster Tool depositions.
    """

    def __init__(self, number=None):
        if number:
            data = connection.open("cluster_tool_depositions/{0}".format(number))
            self.id = data["id"]
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.carrier = data["carrier"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                if layer_data["content_type"] == "institute | cluster tool PECVD layer":
                    ClusterToolPECVDLayer(self, layer_data)
                elif layer_data["content_type"] == "institute | cluster tool hot-wire layer":
                    ClusterToolHotWireLayer(self, layer_data)
                else:
                    raise Exception("{} is an unknown layer type".format(layer_data["content_type"]))
        else:
            self.id = None
            self.sample_ids = []
            self.number = self.operator = self.timestamp = self.comments = None
            self.timestamp_inaccuracy = 0
            self.carrier = None
            self.layers = []
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        if not self.operator:
            self.operator = connection.username
        if self.id is None and self.number is None:
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
            if self.id:
                connection.open("cluster_tool_depositions/{0}/edit/".format(self.number), data)
                logging.info("Edited cluster tool deposition {0}.".format(self.number))
            else:
                self.id = connection.open("cluster_tool_depositions/add/", data)
                logging.info("Added cluster tool deposition {0}.".format(self.number))
        return self.id

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :return:
          all already available deposition numbers

        :rtype: set of str
        """
        return set(connection.open("available_items/ClusterToolDeposition"))


class ClusterToolHotWireLayer:
    """Class representing Cluster Tool hot-wire layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.time = data["time"]
            self.comments = data["comments"]
            self.wire_material = data["wire_material"]
            self.base_pressure = data["base_pressure"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
        else:
            self.time = self.comments = self.wire_material = self.base_pressure = self.h2 = self.sih4 = None

    def get_data(self, layer_index):
        prefix = str(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "step_type": "clustertoolhotwirelayer",
                prefix + "time": self.time,
                prefix + "comments": self.comments,
                prefix + "wire_material": self.wire_material,
                prefix + "base_pressure": self.base_pressure,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4}
        return data


class ClusterToolPECVDLayer:
    """Class representing Cluster Tool PECVD layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.time = data["time"]
            self.comments = data["comments"]
            self.plasma_start_with_shutter = data["plasma_start_with_shutter"]
            self.deposition_power = data["deposition_power"]
            self.h2 = data["h2"]
            self.sih4 = data["sih4"]
        else:
            self.chamber = self.pressure = self.time = self.comments = self.plasma_start_with_shutter = \
                self.deposition_power = self.h2 = self.sih4 = None

    def get_data(self, layer_index):
        prefix = str(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "step_type": "clustertoolpecvdlayer",
                prefix + "chamber": self.chamber,
                prefix + "time": self.time,
                prefix + "comments": self.comments,
                prefix + "plasma_start_with_shutter": self.plasma_start_with_shutter,
                prefix + "deposition_power": self.deposition_power,
                prefix + "h2": self.h2,
                prefix + "sih4": self.sih4}
        return data


def rename_after_deposition(deposition_number, new_names):
    """Rename samples after a deposition.  In some institutes, it is custom to give
    samples the name of the deposition after the deposition.  This is realised
    here.

      `deposition_number`: the number of the deposition
      `new_names`: the new names of the samples.  The keys of this dictionary
        are the sample IDs.  The values are the new names.  Note that they must
        start with the deposition number.

    :type deposition_number: str
    :type new_samples: dict mapping int to str
    """
    data = {}
    for i, id_ in enumerate(new_names):
        data["{0}-sample".format(i)] = id_
        data["{0}-number_of_pieces".format(i)] = 1
        data["0-new_name"] = data["{0}_0-new_name".format(i)] = new_names[id_]
    connection.open("depositions/split_and_rename_samples/" + deposition_number, data)


class PDSMeasurement:
    """Class representing PDS measurements.
    """

    def __init__(self, number=None):
        """Class constructor.
        """
        if number:
            data = connection.open("pds_measurements/{0}".format(number))
            self.id = data["id"]
            self.sample_id = data["samples"][0]
            self.number = data["number"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.apparatus = data["apparatus"]
            self.raw_datafile = data["raw_datafile"]
        else:
            self.id = self.sample_id = self.number = self.operator = self.timestamp = self.comments = self.apparatus = None
            self.timestamp_inaccuracy = 0
            self.raw_datafile = None
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
            if self.id:
                connection.open("pds_measurements/{0}/edit/".format(self.number), data)
                logging.info("Edited PDS measurement {0}.".format(self.number))
            else:
                self.id = connection.open("pds_measurements/add/", data)
                logging.info("Added PDS measurement {0}.".format(self.number))
        return self.id

    @classmethod
    def get_already_available_pds_numbers(cls):
        """Returns the already available PDS numbers.  You must be an
        administrator to use this function.

        :return:
          all already available PDS numbers

        :rtype: set of str
        """
        return set(connection.open("available_items/PDSMeasurement"))


class Substrate:
    """Class representing substrates in the database.
    """

    def __init__(self, initial_data=None):
        """Note that in contrast to other processes, you currently can't retrieve an
        existing substrate from the database (except by retrieving its
        respective sample).
        """
        if initial_data:
            self.id, self.timestamp, self.timestamp_inaccuracy, self.operator, self.external_operator, self.material, \
                self.comments, self.sample_ids = \
                initial_data["ID"], parse_timestamp(initial_data["timestamp"]), \
                initial_data["timestamp_inaccuracy"], initial_data["operator"], initial_data["external_operator"], \
                initial_data["material"], initial_data["comments"], initial_data["samples"]
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
        with TemporaryMySamples(self.sample_ids):
            if self.id:
                connection.open("substrates/{0}/edit/".format(self.id), data)
            else:
                self.id = connection.open("substrates/add/", data)
        return self.id


class SampleNotFound(Exception):
    """Raised if a sample was not found in `get_sample`.  If you catch such an
    exception, you have to fill in the missing attributes of the sample and
    submit it.

    :ivar sample: a newly created `jb_remote.Sample` instance with only the
      name set, and not yet sumbitted to the database.

    :type sample: `jb_remote.Sample`
    """
    def __init__(self, sample):
        super().__init__()
        self.sample = sample

name_pattern = re.compile(r"\d\d[A-Z]-\d{3,4}([-A-Za-z_/][-A-Za-z_/0-9#()]*)?"
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

    :param sample_name: the name of the sample

    :type sample_name: str

    :return:
      the ID of the sample

    :rtype: int

    :raises SampleNotFound: if the sample was not found.  It contains a
        newly created sample and substrate for your convenience.  See the
        documentation of this exception class for more information.
    """

    if not name_pattern.match(sample_name):
        # Build a legacy name with the ``{short_year}-LGCY-`` prefix.
        allowed_sample_name_characters = []
        for character in sample_name:
            if allowed_character_pattern.match(character):
                allowed_sample_name_characters.append(character)
        sample_name = "{}-LGCY-{}".format(str(datetime.datetime.now().year)[2:], "".join(allowed_sample_name_characters)[:30])
    sample_id = connection.open("primary_keys?samples=" + urllib.parse.quote_plus(sample_name))["samples"].get(sample_name)
    if sample_id is not None and not isinstance(sample_id, list):
        return sample_id
    else:
        new_sample = Sample()
        new_sample.name = sample_name
        raise SampleNotFound(new_sample)


class SolarsimulatorMeasurement:

    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("solarsimulator_measurements/{0}".format(process_id))
            self.id = process_id
            self.irradiation = data["irradiation"]
            self.temperature = data["temperature"]
            self.sample_id = data["samples"][0]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.cells = {}
            for key, value in data.items():
                if key.startswith("cell position "):
                    data = value
                    cell = SolarsimulatorCellMeasurement(self, data["position"], data)
        else:
            self.id = self.irradiation = self.temperature = self.sample_id = self.operator = self.timestamp = \
                self.comments = None
            self.timestamp_inaccuracy = 0
            self.cells = {}
        self.edit_important = True
        self.edit_description = None

    def submit(self, only_single_cell_added=False):
        if not self.operator:
            self.operator = connection.username
        data = {"sample": self.sample_id,
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "operator": primary_keys["users"][self.operator],
                "irradiation": self.irradiation,
                "temperature": self.temperature,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, cell in enumerate(self.cells.values()):
            data.update(cell.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.id:
                query_string = "?only_single_cell_added=true" if only_single_cell_added else ""
                connection.open("solarsimulator_measurements/{0}/edit/".format(self.id) + query_string, data)
                logging.info("Edited solarsimulator measurement {0}.".format(self.id))
            else:
                self.id = connection.open("solarsimulator_measurements/add/", data)
                logging.info("Added solarsimulator measurement {0}.".format(self.id))
        return self.id


class SolarsimulatorCellMeasurement:

    def __init__(self, measurement, position, data={}):
        self.position = position
        measurement.cells[position] = self
        if data:
            self.area = data["area"]
            self.eta = data["eta"]
            self.isc = data["isc"]
            self.data_file = data["data_file"]
        else:
            self.area = self.eta = self.isc = self.data_file = None

    def get_data(self, index):
        prefix = str(index) + "-"
        return {prefix + "position": self.position,
                prefix + "area": self.area,
                prefix + "eta": self.eta,
                prefix + "isc": self.isc,
                prefix + "data_file": self.data_file}


class Structuring:

    def __init__(self):
        """Currently, you can only *add* such processes.
        """
        self.sample_id = None
        self.id = None
        self.operator = None
        self.timestamp = None
        self.timestamp_inaccuracy = 0
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
                "layout": self.layout,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        with TemporaryMySamples(self.sample_id):
            if self.id:
                connection.open("structurings/{0}/edit/".format(self.id), data)
                logging.info("Edited structuring {0}.".format(self.id))
            else:
                self.id = connection.open("structurings/add/", data)
                logging.info("Added structuring {0}.".format(self.id))
        return self.id


class FiveChamberDeposition:
    """Class that represents 5-chamber depositions.
    """

    def __init__(self, number=None):
        """Class constructor.

        :param number: if given, the instance represents an existing deposition
            of the database.  Note that this triggers an exception if the
            deposition number is not found in the database.

        :type number: str
        """
        if number:
            data = connection.open("5-chamber_depositions/{0}".format(number))
            self.id = data["id"]
            self.sample_ids = data["samples"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.number = data["number"]
            self.layers = []
            layers = [(int(key[6:]), value) for key, value in data.items() if key.startswith("layer ")]
            for __, layer_data in sorted(layers):
                FiveChamberLayer(self, layer_data)
        else:
            self.id = None
            self.number = None
            self.sample_ids = []
            self.operator = self.timestamp = None
            self.comments = ""
            self.timestamp_inaccuracy = 0
            self.layers = []
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the depositon to the database.

        :return:
          the deposition number if succeeded.

        :rtype: str
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
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for layer_index, layer in enumerate(self.layers):
            data.update(layer.get_data(layer_index))
        with TemporaryMySamples(self.sample_ids):
            if self.id:
                connection.open("5-chamber_depositions/{0}/edit/".format(self.number), data)
                logging.info("Edited 5-chamber deposition {0}.".format(self.number))
            else:
                self.id = connection.open("5-chamber_depositions/add/", data)
                logging.info("Added 5-chamber deposition {0}.".format(self.number))
        return self.id

    @classmethod
    def get_already_available_deposition_numbers(cls):
        """Returns the already available deposition numbers.  You must be an
        administrator to use this function.

        :return:
          all already available deposition numbers

        :rtype: set of str
        """
        return set(connection.open("available_items/FiveChamberDeposition"))


class FiveChamberLayer:
    """Class representing a single 5-chamber layer.
    """

    def __init__(self, deposition, data=None):
        deposition.layers.append(self)
        if data:
            self.chamber = data["chamber"]
            self.temperature_1 = data["temperature_1"]
            self.temperature_2 = data["temperature_2"]
            self.layer_type = data["layer_type"]
            self.sih4 = data["sih4"]
            self.h2 = data["h2"]
        else:
            self.chamber = self.temperature_1 = self.temperature_2 = self.layer_type = \
                self.sih4 = self.h2 = self.silane_concentration = None

    def get_data(self, layer_index):
        prefix = str(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "chamber": self.chamber,
                prefix + "temperature_1": self.temperature_1,
                prefix + "temperature_2": self.temperature_2,
                prefix + "layer_type": self.layer_type,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2}
        return data
