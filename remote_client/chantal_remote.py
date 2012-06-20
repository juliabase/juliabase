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

"""Library for communicating with Chantal through HTTP.  Typical usage is::

    from chantal_remote import *
    login("r.miller", "mysecurepassword")
    new_samples(10, "PECVD lab")
    logout()

This module writes a log file.  On Windows, it is in the current directory.  On
Unix-like systems, it is in /tmp.
"""

from __future__ import unicode_literals
import urllib, urllib2, cookielib, mimetools, mimetypes, json, logging, os.path, datetime, re, time, random, sys, \
    subprocess
import cPickle as pickle

__all__ = ["login", "logout", "new_samples", "Sample", "rename_after_deposition", "PDSMeasurement",
           "get_or_create_sample", "ClusterToolDeposition", "ClusterToolHotWireLayer",
           "ClusterToolPECVDLayer", "PIDLock", "find_changed_files", "defer_files", "send_error_mail",
           "ChantalError", "Result", "setup_logging"]


def setup_logging(enable=False):
    """If the user wants to call this in order to enable logging, he must do
    so before logging in.  Note that it is a no-op if called a second time.
    """
    # This is not totally clean because it doesn't guarantee that logging is
    # properly configured *before* the first log message is generated but I'm
    # pretty sure that this is the case.  The clean solution would involve more
    # boilerplate code for the end-user, which I don't want, or replacing all
    # ``logging.info`` etc. calls with an own wrapper.
    if enable:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)-8s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            filename="/tmp/chantal_remote.log" if os.path.exists("/tmp") else "chantal_remote.log",
                            filemode="w")
    else:
        class LogSink(object):
            def write(self, *args, **kwargs):
                pass
            def flush(self, *args, **kwargs):
                pass
        logging.basicConfig(stream=LogSink())


def clean_header(value):
    """Makes a scalar value fit for being used in POST data.  Note that
    booleans with the value ``False`` are excluded from the POST dictionary by
    returning ``None``.  This mimics HTML's behaviour then ``False`` values in
    forms are “not successful”.
    """
    if isinstance(value, bool):
        return "on" if value else None
    elif isinstance(value, file):
        return value
    else:
        return unicode(value).encode("utf-8")


def comma_separated_ids(ids):
    return ",".join(str(id_) for id_ in ids)


def format_timestamp(timestamp):
    try:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def encode_multipart_formdata(data):
    """Generates content type and body for an HTTP POST request.  It can also
    handle file uploads: For them, the value of the item in ``data`` is an open
    file object.  Taken from <http://code.activestate.com/recipes/146306/#c5>.

    :Parameters:
      - `data`: the POST data; it must not be ``None``

    :type data: dict mapping unicode to unicode, int, float, bool, file, or
      list

    :Return:
      the content type, the HTTP body

    :rtype: str, str
    """
    def get_content_type(filename):
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"

    non_file_items = []
    file_items = []
    for key, value in data.iteritems():
        if isinstance(value, file):
            file_items.append((key, value))
        else:
            if isinstance(value, list):
                for single_value in value:
                    non_file_items.append((key, single_value))
            else:
                non_file_items.append((key, value))
    # Otherwise, we would have to implement multipart/mixed, see
    # http://www.w3.org/TR/html401/interact/forms.html#h-17.13.4.2
    assert len(file_items) <= 1
    if not file_items:
        return "application/x-www-form-urlencoded", urllib.urlencode(data, doseq=True)
    boundary = mimetools.choose_boundary()
    lines = []
    for key, value in non_file_items:
        lines.append("--" + boundary)
        lines.append('Content-Disposition: form-data; name="{0}"'.format(key))
        lines.append("Content-Type: text/plain; charset=utf-8")
        lines.append("")
        lines.append(value)
    if file_items:
        key, value = file_items[0]
        lines.append("--" + boundary)
        filename = os.path.basename(value.name)
        lines.append('Content-Disposition: form-data; name="{0}"; filename="{1}"'.format(key, filename))
        lines.append("Content-Type: {0}".format(get_content_type(filename)))
        lines.append("Content-Transfer-Encoding: binary")
        lines.append("")
        lines.append(value.read())
    lines.append("--" + boundary + "--")
    lines.append("")
    body = "\r\n".join(lines)
    content_type = "multipart/form-data; boundary={0}".format(boundary)
    return content_type, body


class ChantalError(Exception):
    """Exception class for high-level Chantal errors.

    :ivar error_code: The numerical error code.  See ``chantal_common.utils``
      for further information, and the root ``__init__.py`` file of the various
      Chantal apps for the tables with the error codes.

    :ivar error_message: A description of the error.  If `error_code` is ``1``, it
      contains the URL to the error page (without the domain name).

    :type error_code: int
    :type error_message: unicode
    """

    def __init__(self, error_code, message):
        self.error_code, self.error_message = error_code, message

    def __str__(self):
        # FixMe: In Python3, the ``encode`` call must be dropped.
        return "({0}) {1}".format(self.error_code, self.error_message.encode("utf-8"))

    def __unicode__(self):
        return self.__str__()


class PrimaryKeys(object):
    """Dictionary-like class for storing primary keys.  I use this class only
    to delay the costly loading of the primary keys until they are really
    accessed.  This way, GET-request-only usage of the Remote Client becomes
    faster.
    """

    def __init__(self, connection):
        self.connection = connection
        self.primary_keys = None

    def __getitem__(self, key):
        if self.primary_keys is None:
            self.primary_keys = self.connection.open("primary_keys?topics=*&users=*&external_operators=*")
        return self.primary_keys[key]


class ChantalConnection(object):
    """Class for the routines that connect to the database at HTTP level.
    This is a singleton class, and its only instance resides at top-level in
    this module.
    """
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
    opener.addheaders = [("User-agent", "Chantal-Remote/0.1"),
                         ("Accept", "application/json,text/html;q=0.9,application/xhtml+xml;q=0.9,text/*;q=0.8,*/*;q=0.7")]

    def __init__(self, chantal_url="https://chantal.my_institute.kfa-juelich.de/"):
        self.root_url = chantal_url
        self.username = None
        self.primary_keys = PrimaryKeys(self)

    def _do_http_request(self, url, data=None):
        logging.debug("{0} {1!r}".format(url, data))
        if data is None:
            request = urllib2.Request(url)
        else:
            content_type, body = encode_multipart_formdata(data)
            headers = {"Content-Type": content_type}
            request = urllib2.Request(url, body, headers)
        max_cycles = 10
        while max_cycles > 0:
            max_cycles -= 1
            try:
                return self.opener.open(request)
            except urllib2.HTTPError as error:
                if error.code in [404, 422] and error.info()["Content-Type"].startswith("application/json"):
                    error_code, error_message = json.loads(error.read())
                    raise ChantalError(error_code, error_message)
                try:
                    open("/tmp/chantal_error.html", "w").write(error.read())
                except IOError:
                    pass
                raise error
            except urllib2.URLError:
                if max_cycles == 0:
                    logging.error("Request failed.")
                    raise
            time.sleep(3 * random.random())

    def open(self, relative_url, data=None, response_is_json=True):
        """Do an HTTP request with the Chantal server.  If ``data`` is not
        ``None``, its a POST request, and GET otherwise.

        :Parameters:
          - `relative_url`: the non-domain part of the URL, for example
            ``"/samples/10-TB-1"``.  “Relative” may be misguiding here: only
            the domain is omitted.
          - `data`: the POST data, or ``None`` if it's supposed to be a GET
            request.
          - `response_is_json`: whether the content type of the response must
            be JSON

        :type relative_url: str
        :type data: dict mapping unicode to unicode, int, float, bool, file, or
          list
        :type response_is_json: bool

        :Return:
          the response to the request

        :rtype: ``object``

        :Exceptions:
          - `ChantalError`: raised if Chantal couldn't fulfill the request
            because it contained errors.  For example, you requested a sample
            that doesn't exist, or the transmitted measurement data was
            incomplete.
          - `urllib2.URLError`: raise if a lower-level error occured, e.g. the
            HTTP connection couldn't be established.
        """
        if data is not None:
            cleaned_data = {}
            for key, value in data.iteritems():
                key = clean_header(key)
                if value is not None:
                    if not isinstance(value, list):
                        cleaned_header = clean_header(value)
                        if cleaned_header:
                            cleaned_data[key] = cleaned_header
                    else:
                        cleaned_list = [clean_header(item) for item in value if value is not None]
                        if cleaned_list:
                            cleaned_data[key] = cleaned_list
            response = self._do_http_request(self.root_url + relative_url, cleaned_data)
        else:
            response = self._do_http_request(self.root_url + relative_url)
        if response_is_json:
            assert response.info()["Content-Type"].startswith("application/json")
            return json.loads(response.read())
        else:
            return response.read()

    def login(self, username, password):
        self.username = username
        self.open("login_remote_client", {"username": username, "password": password})

    def logout(self):
        self.open("logout_remote_client")


connection = ChantalConnection()


def login(username, password, testserver=False):
    """Logins to Chantal.

    :Parameters:
      - `username`: the username used to log in
      - `password`: the user's password
      - `testserver`: whether the testserver should be user.  If ``False``, the
        production server is used.

    :type username: unicode
    :type password: unicode
    :type testserver: bool
    """
    setup_logging()
    if testserver:
        logging.info("Logging into the testserver.")
        connection.root_url = "http://my_testserver.my_institute.kfa-juelich.de/"
    connection.login(username, password)
    logging.info("Successfully logged-in as {0}.".format(username))


def logout():
    """Logs out of Chantal.
    """
    connection.logout()
    logging.info("Successfully logged-out.")


class TemporaryMySamples(object):
    """Context manager for adding samples to the “My Samples” list
    temporarily.  This is used when editing or adding processes.  In order to
    be able to link the process with samples, they must be on your “My Samples”
    list.

    This context manager should be used linke this::

        with TemporaryMySamples(sample_ids):
            ...

    The code at ``...`` can safely assume that the ``sample_ids`` have been
    added to “My Samples”.  After having execuded this code, those samples that
    hadn't been on “My Samples” already are removed from “My Samples”.  This
    way, the “My Samples” list is unchanged eventually.
    """

    def __init__(self, sample_ids):
        """Class constructor.

        :Parameters:
          `sample_ids`: the IDs of the samples that must be on the “My Samples”
            list; it my also be a single ID

        :type sample_ids: list of int or int
        """
        self.sample_ids = sample_ids if isinstance(sample_ids, (list, tuple, set)) else [sample_ids]

    def __enter__(self):
        self.changed_sample_ids = connection.open("change_my_samples", {"add": comma_separated_ids(self.sample_ids)})

    def __exit__(self, type_, value, tb):
        if self.changed_sample_ids:
            connection.open("change_my_samples", {"remove": comma_separated_ids(self.changed_sample_ids)})


def new_samples(number_of_samples, current_location, substrate="asahi-u", timestamp=None, timestamp_inaccuracy=None,
                purpose=None, tags=None, topic=None, substrate_comments=None):
    """Creates new samples in the database.  All parameters except the number
    of samples and the current location are optional.

    :Parameters:
      - `number_of_samples`: the number of samples to be created.  It must not
        be greater than 100.
      - `current_location`: the current location of the samples
      - `substrate`: the substrate of the samples.  You find possible values in
        `models_physical_processes`.
      - `timestamp`: the timestamp of the substrate process; defaults to the
        current time
      - `timestamp_inaccuracy`: the timestamp inaccuracy of the substrate
        process.  See ``samples.models_common`` for details.
      - `purpose`: the purpose of the samples
      - `tags`: the tags of the samples
      - `topic`: the name of the topic of the samples
      - `substrate_comments`: Further comments on the substrate process

    :type number_of_samples: int
    :type current_location: unicode
    :type substrate: unicode
    :type timestamp: unicode
    :type timestamp_inaccuracy: unicode
    :type purpose: unicode
    :type tags: unicode
    :type topic: unicode
    :type substrate_comments: unicode

    :Return:
      the IDs of the generated samples

    :rtype: list of int
    """
    samples = connection.open("samples/add/",
                              {"number_of_samples": number_of_samples,
                               "current_location": current_location,
                               "timestamp": format_timestamp(timestamp),
                               "timestamp_inaccuracy": timestamp_inaccuracy or 0,
                               "substrate": substrate,
                               "substrate_comments": substrate_comments,
                               "purpose": purpose,
                               "tags": tags,
                               "topic": connection.primary_keys["topics"].get(topic),
                               "currently_responsible_person":
                                   connection.primary_keys["users"][connection.username]})
    logging.info("Successfully created {number} samples with the ids {ids}.".format(
            number=len(samples), ids=comma_separated_ids(samples)))
    return samples


class Result(object):

    def __init__(self, id_=None, with_image=True):
        """Class constructor.

        :Parameters:
          - `id_`: if given, the instance represents an existing result process
            of the database.  Note that this triggers an exception if the
            result ID is not found in the database.
          - `with_image`: whether the image data should be loaded, too

        :type id_: int or unicode
        :type with_image: bool
        """
        if id_:
            self.id = id_
            data = connection.open("results/{0}".format(id_))
            self.sample_ids = data["sample IDs"]
            self.sample_series = data["sample series"]
            self.operator = data["operator"]
            self.timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            self.timestamp_inaccuracy = data["timestamp inaccuracy"]
            self.comments = data["comments"]
            self.title = data["title"]
            self.image_type = data["image type"]
            if self.image_type != "none" and with_image:
                self.image_data = connection.open("results/images/{0}".format(id_), response_is_json=False)
            self.external_operator = data["external operator"]
            self.quantities_and_values = data["quantities and values"]
            self.existing = True
        else:
            self.id = None
            self.sample_ids = []
            self.sample_series = []
            self.external_operator = self.operator = self.timestamp = self.comments = self.title = self.image_type = None
            self.timestamp_inaccuracy = 0
            self.quantities_and_values = []
            self.existing = False
        self.image_filename = None
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the result to the database.

        :Return:
          the result process ID if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        number_of_quantities = len(self.quantities_and_values)
        number_of_values = number_of_quantities and len(self.quantities_and_values[0][1])
        data = {"finished": self.finished,
                "operator": connection.primary_keys["users"][self.operator],
                "timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "comments": self.comments,
                "title": self.title,
                "samples": self.sample_ids,
                "sample_series": self.sample_series,
                "number_of_quantities": number_of_quantities,
                "number_of_values": number_of_values,
                "previous-number_of_quantities": number_of_quantities,
                "previous-number_of_values": number_of_values,
                "remove_from_my_samples": False,
                "external_operator": self.external_operator and \
                    connection.primary_keys["external_operators"][self.external_operator],
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for i, quantity_and_values in enumerate(self.quantities_and_values):
            quantity, values = quantity_and_values
            data["{0}-quantity".format(i)] = quantity
            for j, value in enumerate(values):
                data["{0}_{1}-value".format(i, j)] = value
        if self.image_filename:
            data["image_file"] = open(self.image_filename)
        with TemporaryMySamples(self.sample_ids):
            if self.existing:
                result = connection.open("results/{0}/edit/".format(self.id), data)
            else:
                result = connection.open("results/add/", data)
                logging.info("Successfully added result {0}.".format(self.id))
        return result


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
            layers = [(int(key[6:]), value) for key, value in data.iteritems() if key.startswith("layer ")]
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
                "operator": connection.primary_keys["users"][self.operator],
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
        prefix = unicode(layer_index) + "-"
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
        prefix = unicode(layer_index) + "-"
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
                "operator": connection.primary_keys["users"][self.operator],
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
            self.id = self.timestamp = self.timestamp_inaccuracy = self.operator = self.external_operator = self.material = \
                self.comments = None
            self.sample_ids = []

    def submit(self):
        data = {"timestamp": format_timestamp(self.timestamp),
                "timestamp_inaccuracy": self.timestamp_inaccuracy,
                "material": self.material,
                "comments": self.comments,
                "operator": connection.primary_keys["users"][self.operator],
                "external_operator": self.external_operator and \
                    connection.primary_keys["external_operators"][self.external_operator],
                "sample_list": self.sample_ids}
        if self.id:
            data["edit_description-description"] = "automatic change by a non-interactive program"
            connection.open("substrates/{0}/edit/".format(self.id), data)
        else:
            return connection.open("substrates/add/", data)


class Sample(object):
    """Class representing samples.
    """

    def __init__(self, name=None, id_=None):
        """Class constructor.

        :Parameters:
          - `name`: the name of an existing sample; it is ignored if `id_` is
            given
          - `id_`: the ID of an existing sample

        :type name: unicode
        :type id_: int
        """
        if name or id_:
            data = connection.open("samples/by_id/{0}".format(id_)) if id_ else \
                connection.open("samples/{0}".format(urllib.quote(name)))
            self.id = data["ID"]
            self.name = data["name"]
            self.current_location = data["current location"]
            self.currently_responsible_person = data["currently responsible person"]
            self.purpose = data["purpose"]
            self.tags = data["tags"]
            self.topic = data["topic"]
            self.processes = dict((key, value) for key, value in data.iteritems() if key.startswith("process "))
        else:
            self.id = self.name = self.current_location = self.currently_responsible_person = self.purpose = self.tags = \
                self.topic = self.timestamp = None
        self.legacy = False
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        data = {"name": self.name, "current_location": self.current_location,
                "currently_responsible_person": connection.primary_keys["users"][self.currently_responsible_person],
                "purpose": self.purpose, "tags": self.tags,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        if self.topic:
            data["topic"] = connection.primary_keys["topics"][self.topic]
        if self.id:
            connection.open("samples/by_id/{0}/edit/".format(self.id), data)
        else:
            if not self.timestamp:
                self.timestamp = datetime.datetime(1990, 1, 1)
            return connection.open("add_sample?" + urllib.urlencode(
                    {"legacy": self.legacy, "timestamp": format_timestamp(self.timestamp)}), data)

    def add_to_my_samples(self):
        connection.open("change_my_samples", {"add": self.id})

    def remove_from_my_samples(self):
        connection.open("change_my_samples", {"remove": self.id})


main_sample_name_pattern = re.compile(r"(?P<year>\d\d)(?P<letter>[ABCDEFHKLNOPQSTVWXYabcdefhklnopqstvwxy])-?"
                                      r"(?P<number>\d{1,4})(?P<suffix>[-A-Za-z_/#()][-A-Za-z_/0-9#()]*)?$")
allowed_character_pattern = re.compile("[-A-Za-z_/0-9#()]")

def normalize_sample_name(sample_name):
    """Normalises a sample name.  Unfortunately, co-workers tend to write
    sample names in many variations.  For example, instead of 10B-010, they
    write 10b-010 or 10b010 or 10B-10.  In this routine, I normalise to known
    sample patterns.  Additionally, if a known pattern is found, this routine
    makes suggestions for the currently reponsible person, the topic, and some
    other things.

    This routine is used in crawlers and legacy importers.

    :Parameter:
      - `sample_name`: the raw name of the sample

    :type sample_name: unicode

    :Return:
      The normalised sample data.  The keys of this dictionary are ``"name"``
      (this is the normalised name), ``"currently_responsible_person"``,
      ``"current_location"``, ``"substrate_operator"``,
      ``"substrate_external_operator"``, ``"topic"``, and ``"legacy"``.  The
      latter is a boolean denoting whether the database must prepend a legacy
      prefix à la “10-LGCY--” when creating the sample.

    :rtype: dict mapping str to unicode
    """
    result = {"currently_responsible_person": "nobody", "substrate_operator": "nobody", "substrate_external_operator": None,
              "legacy": True, "current_location": "unknown", "topic": "Legacy", "alias": None}

    sample_name = " ".join(sample_name.split())
    translations = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
                    " ": "_", "°": "o"}
    for from_, to in translations.iteritems():
        sample_name = sample_name.replace(from_, to)
    allowed_sample_name_characters = []
    for character in sample_name:
        if allowed_character_pattern.match(character):
            allowed_sample_name_characters.append(character)
    result["name"] = "".join(allowed_sample_name_characters)[:30]
    current_year = int(datetime.datetime.now().strftime("%y"))
    match = main_sample_name_pattern.match(sample_name)
    if match and int(match.group("year")) <= current_year:
        parts = match.groupdict("")
        parts["number"] = "{0:03}".format(int(parts["number"]))
        parts["letter"] = parts["letter"].upper()
        if parts["letter"] == "D":
            result["current_location"] = "02.4u/82b, Schrank hinter Flasher"
            result["topic"] = "LADA intern"
            parts["number"] = "{0:04}".format(int(parts["number"]))
        result["name"] = "{year}{letter}-{number}{suffix}".format(**parts)
        result["legacy"] = False
        return result
    return result


class SubstrateFound(Exception):
    """Exception raised for simpler control flow in
    `normalize_substrate_name`.  It is only used there.
    """
    def __init__(self, key_name, substrate_comments):
        self.key_name, self.substrate_comments = key_name, substrate_comments

unknown_substrate_comment = "unknown substrate material"

def normalize_substrate_name(substrate_name, is_general_comment=False, add_zno_warning=False):
    """Normalises a substrate name to data directly usable for the sample
    database.

    :Parameters:
      - `substrate_name`: a string which contains information about the substrate
      - `is_general_comment`: whether `substrate_name` is a general comment
        containing the substrate name somewhere, or only the substrate name
        (albeit in raw form)
      - `add_zno_warning`: whether a warning should be issued if the sample
        probably had a ZnO process (because such processes are not yet in the
        database)

    :type substrate_name: unicode
    :type is_general_comment: bool
    :type add_zno_warning: bool

    :Return:
      the substrate name as needed by Chantal, comments of the substrate
      process

    :rtype: unicode, unicode
    """
    substrate_name = " ".join(substrate_name.split())
    normalized_substrate_name = substrate_name.lower().replace("-", " ").replace("(", ""). \
        replace(")", "")
    normalized_substrate_name = " ".join(normalized_substrate_name.split())
    def test_name(pattern, key_name, comment=""):
        if re.match("^({0})$".format(pattern), normalized_substrate_name, re.UNICODE):
            raise SubstrateFound(key_name, comment)
        elif re.search(pattern, normalized_substrate_name, re.UNICODE):
            raise SubstrateFound(key_name, substrate_name if not is_general_comment else comment)
    try:
        if not normalized_substrate_name:
            raise SubstrateFound("custom", unknown_substrate_comment)
        test_name("asahi ?vu|asahi ?uv", "asahi-vu")
        test_name("asahi|ashi", "asahi-u")
        test_name("corning|coaring", "corning")
        test_name("eagle ?(2000|xg)", "corning", "Eagle 2000")
        test_name("quartz|quarz", "quartz")
        test_name("ilmasil", "quartz", "Ilmasil")
        test_name("qsil", "quartz", "Qsil")
        test_name("sapphire|saphir|korund|corundum", "sapphire")
        test_name("glas", "glass")
        test_name(r"\balu", "aluminium foil")
        test_name(r"\bsi\b.*wafer|wafer.*\bsi\b|silicon.*wafer|wafer.*silicon|c ?si", "si-wafer")
        raise SubstrateFound("custom", substrate_name if not is_general_comment else unknown_substrate_comment)
    except SubstrateFound as found_substrate:
        key_name, substrate_comments = found_substrate.key_name, found_substrate.substrate_comments
        if add_zno_warning and "zno" in normalized_substrate_name:
            if substrate_comments:
                substrate_comments += "\n\n"
            substrate_comments += "ZnO may have been applied to the substrate without an explicitly shown sputter process."
        return key_name, substrate_comments


def get_or_create_sample(sample_name, substrate_name, timestamp, timestamp_inaccuracy="3", comments=None,
                         add_zno_warning=False, create=True):
    """Looks up a sample name in the database, and creates a new one if it
    doesn't exist yet.  You can only use this function if you are an
    administrator.  This function is used in crawlers and legacy importers.
    The sample is added to “My Samples”.

    :Parameters:
      - `sample_name`: the name of the sample
      - `substrate_name`: the concise descriptive name of the substrate.  This
        routine tries heavily to normalise it.
      - `timestamp`: the timestamp of the sample/substrate
      - `timestamp_inaccuracy`: the timestamp inaccuracy of the
        sample/substrate
      - `comments`: Comment which may contain information about the substrate.
        They are ignored if `substrate_name` is given.  In a way, this
        parameter is a poor man's `substrate_name`.
      - `add_zno_warning`: whether a warnign should be issued if the sample
        probably had a ZnO process (because such processes are not yet in the
        database)
      - `create`: if ``True``, create the sample if it doesn't exist yet; if
        ``False``, return ``None`` if the sample coudn't be found

    :type sample_name: unicode
    :type substrate_name: unicode or ``NoneType``
    :type timestamp_inaccuracy: unicode
    :type comments: unicode
    :type add_zno_warning: bool

    :Return:
      the ID of the sample, either the existing or the newly created; or
      ``None`` if ``create=False`` and the sample could not be found

    :rtype: int or ``NoneType``
    """
    name_info = normalize_sample_name(sample_name)
    substrate_material, substrate_comments = normalize_substrate_name(substrate_name or comments or "",
                                                                      is_general_comment=not substrate_name,
                                                                      add_zno_warning=add_zno_warning)
    if name_info["name"] != "unknown_name":
        sample_id = connection.open("primary_keys?samples=" + urllib.quote_plus(name_info["name"]))["samples"].\
            get(name_info["name"])
        if not sample_id and name_info["legacy"]:
            sample_name = "{year}-LGCY--{name}".format(year=timestamp.strftime("%y"), name=name_info["name"])[:30]
            sample_id = connection.open("primary_keys?samples=" + urllib.quote_plus(sample_name))["samples"].\
                get(sample_name)
        if name_info["legacy"]:
            if sample_id is not None:
                best_match = {}
                sample_ids = sample_id if isinstance(sample_id, list) else [sample_id]
                for sample_id in sample_ids:
                    substrate_data = connection.open("substrates_by_sample/{0}".format(sample_id))
                    if substrate_data:
                        current_substrate = Substrate(substrate_data)
                        timedelta = abs(current_substrate.timestamp - timestamp)
                        if timedelta < datetime.timedelta(weeks=104) and \
                                ("timedelta" not in best_match or timedelta < best_match["timedelta"]):
                            best_match["timedelta"] = timedelta
                            best_match["id"] = sample_id
                            best_match["substrate"] = current_substrate
                sample_id = best_match.get("id")
                substrate = best_match.get("substrate")
        else:
            if isinstance(sample_id, list):
                sample_id = None
            elif sample_id is not None:
                substrate = Substrate(connection.open("substrates_by_sample/{0}".format(sample_id)))
                assert substrate.timestamp, Exception("sample ID {0} had no substrate".format(sample_id))
    else:
        sample_id = None
    if sample_id is None:
        if create:
            new_sample = Sample()
            new_sample.name = name_info["name"]
            new_sample.current_location = name_info["current_location"]
            new_sample.currently_responsible_person = name_info["currently_responsible_person"]
            new_sample.topic = name_info["topic"]
            new_sample.legacy = name_info["legacy"]
            new_sample.timestamp = timestamp
            sample_id = new_sample.submit()
            assert sample_id, Exception("Could not create sample {0}".format(name_info["name"]))
            substrate = Substrate()
            substrate.timestamp = timestamp - datetime.timedelta(seconds=2)
            substrate.timestamp_inaccuracy = timestamp_inaccuracy
            substrate.material = substrate_material
            substrate.comments = substrate_comments
            substrate.operator = name_info["substrate_operator"]
            substrate.sample_ids = [sample_id]
            if name_info["substrate_external_operator"]:
                substrate.external_operator = name_info["substrate_external_operator"]
            substrate.submit()
    else:
        connection.open("change_my_samples", {"add": sample_id})
        substrate_changed = False
        if substrate.timestamp > timestamp:
            substrate.timestamp = timestamp - datetime.timedelta(seconds=2)
            substrate.timestamp_inaccuracy = timestamp_inaccuracy
            substrate_changed = True
        if substrate.material == "custom" and substrate.comments == unknown_substrate_comment:
            substrate.material = substrate_material
            substrate.comments = substrate_comments
            substrate_changed = True
        else:
            if substrate.material != substrate_material:
                additional_substrate_comments = substrate_comments if substrate_material == "custom" else substrate_material
            elif substrate_material == "custom":
                additional_substrate_comments = substrate_comments
            else:
                additional_substrate_comments = None
            if additional_substrate_comments:
                if substrate.comments:
                    substrate.comments += "\n\n"
                substrate_comments += "Alternative information: " + additional_substrate_comments
                substrate_changed = True
        if substrate_changed:
            substrate.submit()
    return sample_id


class PIDLock(object):
    """Class for process locking in with statements.  You can use this class
    like this::

        with PIDLock("my_program") as locked:
            if locked:
                do_work()
            else:
                print "I'am already running.  I just exit."

    The parameter ``"my_program"`` is used for determining the name of the PID
    lock file.
    """

    def __init__(self, name):
        self.lockfile_path = os.path.join("/tmp/", name + ".pid")
        self.locked = False

    def __enter__(self):
        import fcntl  # local because only available on Unix
        try:
            self.lockfile = open(self.lockfile_path, "r+")
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            pid = int(self.lockfile.read().strip())
        except IOError as e:
            if e.strerror == "No such file or directory":
                self.lockfile = open(self.lockfile_path, "w")
                fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX)
                already_running = False
            elif e.strerror == "Resource temporarily unavailable":
                already_running = True
                sys.stderr.write("WARNING: Lock {0} of other process active\n".format(self.lockfile_path))
            else:
                raise
        except ValueError:
            # Ignore invalid lock
            already_running = False
            self.lockfile.seek(0)
            self.lockfile.truncate()
            sys.stderr.write("ERROR: Lock {0} of other process has invalid content\n".format(self.lockfile_path))
        else:
            try:
                os.kill(pid, 0)
            except OSError as error:
                if error.strerror == "No such process":
                    # Ignore invalid lock
                    already_running = False
                    self.lockfile.seek(0)
                    self.lockfile.truncate()
                    sys.stderr.write("WARNING: Lock {0} of other process is orphaned\n".format(self.lockfile_path))
                else:
                    raise
            else:
                # sister process is already active
                already_running = True
                sys.stderr.write("WARNING: Lock {0} of other process active (but strangely not locked)\n".
                                 format(self.lockfile_path))
        if not already_running:
            self.lockfile.write(str(os.getpid()))
            self.lockfile.flush()
            self.locked = True
        return self.locked

    def __exit__(self, type_, value, tb):
        import fcntl
        if self.locked:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
            self.lockfile.close()
            os.remove(self.lockfile_path)
            logging.info("Removed lock {0}".format(self.lockfile_path))


def find_changed_files(root, diff_file, pattern=""):
    """Returns the files changed or removed since the last run of this
    function.  The files are given as a list of absolute paths.  Changed files
    are files which have been added or modified.  If a file was moved, the new
    path is returned in the “changed” list, and the old one in the “removed”
    list.  Changed files are sorted by timestamp, oldest first.

    If you move all files to another root and give that new root to this
    function, still only the modified files are returned.  In other words, the
    modification status of the last run only refers to file paths relative to
    ``root``.

    :Parameters:
      - `root`: absolute root path of the files to be scanned
      - `diff_file`: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
      - `pattern`: Regular expression for filenames (without path) that should
        be scanned.  By default, all files are scanned.

    :type root: str
    :type diff_file: str
    :type pattern: unicode

    :Return:
      files changed, files removed

    :rtype: list of str, list of str
    """
    compiled_pattern = re.compile(pattern, re.IGNORECASE)
    if os.path.exists(diff_file):
        statuses, last_pattern = pickle.load(open(diff_file, "rb"))
        if last_pattern != pattern:
            for relative_filepath in [relative_filepath for relative_filepath in statuses
                                      if not compiled_pattern.match(os.path.basename(relative_filepath))]:
                del statuses[relative_filepath]
    else:
        statuses, last_pattern = {}, None
    touched = []
    found = set()
    for dirname, __, filenames in os.walk(root):
        for filename in filenames:
            if compiled_pattern.match(filename):
                filepath = os.path.join(dirname, filename)
                relative_filepath = os.path.relpath(filepath, root)
                found.add(relative_filepath)
                mtime = os.path.getmtime(filepath)
                status = statuses.setdefault(relative_filepath, [None, None])
                if mtime != status[0]:
                    status[0] = mtime
                    touched.append(filepath)
    removed = set(statuses) - found
    for relative_filepath in removed:
        del statuses[relative_filepath]
    removed = [os.path.join(root, relative_filepath) for relative_filepath in removed]
    changed = []
    timestamps = {}
    if touched:
        xargs_process = subprocess.Popen(["xargs", "-0", "md5sum"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        xargs_output = xargs_process.communicate(b"\0".join(touched))[0]
        if xargs_process.returncode != 0:
            raise subprocess.CalledProcessError(xargs_process.returncode, "xargs")
        for line in xargs_output.splitlines():
            md5sum, __, filepath = line.partition(b"  ")
            status = statuses[os.path.relpath(filepath, root)]
            if md5sum != status[1]:
                status[1] = md5sum
                changed.append(filepath)
                timestamps[filepath] = status[0]
    changed.sort(key=lambda filepath: timestamps[filepath])
    if touched or removed or last_pattern != pattern:
        pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)
    return changed, removed


def defer_files(diff_file, filepaths):
    """Removes filepaths from a diff file created by `find_changed_files`.
    This is interesting if you couldn't process certain files so they should be
    re-visited in the next run of the crawler.  Typical use case: Some
    measurement files could not be processed because the sample was not found
    in Chantal.  Then, this sample is added to Chantal, and the files should be
    processed although they haven't changed.

    If the file is older than 12 weeks, it is not defered.

    If a filepath is not found in the diff file, this is ignored.

    :Parameters:
      - `diff_file`: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
      - `filepaths`: all relative paths that should be removed from the diff
        file; they are relative to the root that was used when creating the
        diff file;  see `find_changed_files`

    :type diff_file: str
    :type filepaths: iterable of str
    """
    statuses, pattern = pickle.load(open(diff_file, "rb"))
    twelve_weeks_ago = time.time() - 12 * 7 * 24 * 3600
    for filepath in filepaths:
        if filepath in statuses and statuses[filepath][0] > twelve_weeks_ago:
            del statuses[filepath]
    pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)


def send_error_mail(from_, subject, text, html=None):
    """Sends an email to Chantal's administrators.  Normally, it is about an
    error condition but it may be anything.

    :Parameters:
      - `from_`: name (and only the name, not an email address) of the sender;
        this typically is the name of the currently running program
      - `subject`: the subject of the message
      - `text`: text body of the message
      - `html`: optional HTML attachment

    :type from_: unicode
    :type subject: unicode
    :type text: unicode
    :type html: unicode
    """
    # Make these imports lazy, at least as long as this module hasn't been
    # split up into smaller modules.
    import smtplib, email
    from email.MIMEMultipart import MIMEMultipart
    from email.MIMEText import MIMEText
    cycles = 5
    while cycles:
        try:
            server = smtplib.SMTP()
            server.connect("mailrelay.fz-juelich.de")
            message = MIMEMultipart()
            message["Subject"] = subject
            message["From"] = '"{0}" <t.bronger@fz-juelich.de>'. \
                format(from_.replace('"', "")).encode("ascii", "replace")
            message["To"] = "chantal-admins@googlegroups.com"
            message["Date"] = email.Utils.formatdate()
            message.attach(MIMEText(text.encode("utf-8"), _charset="utf-8"))
            if html:
                message.attach(MIMEText(html.encode("utf-8"), "html", _charset="utf-8"))
            server.sendmail("t.bronger@fz-juelich.de", message["To"], message.as_string())
            server.quit()
        except smtplib.SMTPException:
            pass
        else:
            break
        cycles -= 1
        time.sleep(10)


class SolarsimulatorPhotoMeasurement(object):

    def __init__(self, process_id=None):
        if process_id:
            data = connection.open("solarsimulator_measurements/photo/{0}".format(process_id))
            self.process_id = process_id
            self.irradiance = data["irradiance"]
            self.temperature = data["temperature/degC"]
            self.sample_id = data["sample IDs"][0]
            self.operator = data["operator"]
            self.timestamp = datetime.datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S")
            self.timestamp_inaccuracy = data["timestamp inaccuracy"]
            self.comments = data["comments"]
            self.cells = {}
            for key, value in data.iteritems():
                if key.startswith("cell position "):
                    cell = PhotoCellMeasurement(value)
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
                "operator": connection.primary_keys["users"][self.operator],
                "irradiance": self.irradiance,
                "temperature": self.temperature,
                "comments": self.comments,
                "remove_from_my_samples": False,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for index, cell in enumerate(self.cells.itervalues()):
            data.update(cell.get_data(index))
        with TemporaryMySamples(self.sample_id):
            if self.existing:
                query_string = "?only_single_cell_added=true" if only_single_cell_added else ""
                connection.open("solarsimulator_measurements/photo/{0}/edit/".format(self.process_id) + query_string, data)
            else:
                return connection.open("solarsimulator_measurements/photo/add/", data)


class PhotoCellMeasurement(object):

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
        prefix = unicode(index) + "-"
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
                "operator": connection.primary_keys["users"][self.operator],
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
            layers = [(int(key[6:]), value) for key, value in data.iteritems() if key.startswith("layer ")]
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
                "operator": connection.primary_keys["users"][self.operator],
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
        prefix = unicode(layer_index) + "-"
        data = {prefix + "number": layer_index + 1,
                prefix + "chamber": self.chamber,
                prefix + "temperature_1": self.temperature_1,
                prefix + "temperature_2": self.temperature_2,
                prefix + "date": self.date,
                prefix + "layer_type": self.layer_type,
                prefix + "sih4": self.sih4,
                prefix + "h2": self.h2}
        return data
