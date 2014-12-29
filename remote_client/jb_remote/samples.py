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

from __future__ import absolute_import, unicode_literals, division

import json
from .common import connection, primary_keys, comma_separated_ids, double_urlquote, format_timestamp, parse_timestamp, logging


primary_keys.components.add("external_operators=*")


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

    :param number_of_samples: the number of samples to be created.  It must not
        be greater than 100.
    :param current_location: the current location of the samples
    :param substrate: the substrate of the samples.  You find possible values in
        `models.physical_processes`.
    :param timestamp: the timestamp of the substrate process; defaults to the
        current time
    :param timestamp_inaccuracy: the timestamp inaccuracy of the substrate
        process.  See ``samples.models.common`` for details.
    :param purpose: the purpose of the samples
    :param tags: the tags of the samples
    :param topic: the name of the topic of the samples
    :param substrate_comments: Further comments on the substrate process

    :type number_of_samples: int
    :type current_location: unicode
    :type substrate: unicode
    :type timestamp: unicode
    :type timestamp_inaccuracy: unicode
    :type purpose: unicode
    :type tags: unicode
    :type topic: unicode
    :type substrate_comments: unicode

    :return:
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
                               "topic": primary_keys["topics"].get(topic),
                               "currently_responsible_person":
                                   primary_keys["users"][connection.username]})
    logging.info("Successfully created {number} samples with the ids {ids}.".format(
            number=len(samples), ids=comma_separated_ids(samples)))
    return samples


class Sample(object):
    """Class representing samples.
    """

    def __init__(self, name=None, id_=None):
        """Class constructor.

        :param name: the name of an existing sample; it is ignored if `id_` is
            given
        :param id_: the ID of an existing sample

        :type name: unicode
        :type id_: int
        """
        if name or id_:
            data = connection.open("samples/by_id/{0}".format(id_)) if id_ else \
                connection.open("samples/{0}".format(double_urlquote(name)))
            self.id = data["id"]
            self.name = data["name"]
            self.current_location = data["current_location"]
            self.currently_responsible_person = data["currently_responsible_person"]
            self.purpose = data["purpose"]
            self.tags = data["tags"]
            self.topic = data["topic"]
            self.processes = dict((key, value) for key, value in data.items() if key.startswith("process "))
        else:
            self.id = self.name = self.current_location = self.currently_responsible_person = self.purpose = self.tags = \
                self.topic = None
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        data = {"name": self.name, "current_location": self.current_location,
                "currently_responsible_person": primary_keys["users"][self.currently_responsible_person],
                "purpose": self.purpose, "tags": self.tags,
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        if self.topic:
            data["topic"] = primary_keys["topics"][self.topic]
        if self.id:
            connection.open("samples/by_id/{0}/edit/".format(self.id), data)
            logging.info("Edited sample {0}.".format(self.name))
        else:
            self.id = connection.open("add_sample", data)
            logging.info("Added sample {0}.".format(self.name))
        return self.id

    def add_to_my_samples(self, user=None):
        data = {"add": self.id}
        if user:
            data["user"] = primary_keys["users"][user]
        connection.open("change_my_samples", data)

    def remove_from_my_samples(self, user=None):
        data = {"remove": self.id}
        if user:
            data["user"] = primary_keys["users"][user]
        connection.open("change_my_samples", data)


class Result(object):

    def __init__(self, id_=None, with_image=True):
        """Class constructor.

        :param id_: if given, the instance represents an existing result process
            of the database.  Note that this triggers an exception if the
            result ID is not found in the database.
        :param with_image: whether the image data should be loaded, too

        :type id_: int or unicode
        :type with_image: bool
        """
        if id_:
            self.id = id_
            data = connection.open("results/{0}".format(id_))
            self.sample_ids = data["samples"]
            self.sample_series = data["sample_series"]
            self.operator = data["operator"]
            self.timestamp = parse_timestamp(data["timestamp"])
            self.timestamp_inaccuracy = data["timestamp_inaccuracy"]
            self.comments = data["comments"]
            self.title = data["title"]
            self.image_type = data["image_type"]
            if self.image_type != "none" and with_image:
                self.image_data = connection.open("results/images/{0}".format(id_), response_is_json=False)
            self.external_operator = data["external_operator"]
            self.quantities, self.values = json.loads(data["quantities_and_values"])
        else:
            self.id = None
            self.sample_ids = []
            self.sample_series = []
            self.external_operator = self.operator = self.timestamp = self.comments = self.title = self.image_type = None
            self.timestamp_inaccuracy = 0
            self.quantities = []
            self.values = []
        self.image_filename = None
        self.finished = True
        self.edit_description = None
        self.edit_important = True

    def submit(self):
        """Submit the result to the database.

        :return:
          the result process ID if succeeded.

        :rtype: unicode
        """
        if not self.operator:
            self.operator = connection.username
        number_of_quantities = len(self.quantities)
        number_of_values = number_of_quantities and len(self.values[0])
        data = {"finished": self.finished,
                "operator": primary_keys["users"][self.operator],
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
                    primary_keys["external_operators"][self.external_operator],
                "edit_description-description": self.edit_description,
                "edit_description-important": self.edit_important}
        for i, quantity in enumerate(self.quantities):
            data["{0}-quantity".format(i)] = quantity
        for i, column in enumerate(self.values):
            for j, value in enumerate(column):
                data["{0}_{1}-value".format(j, i)] = value
        if self.image_filename:
            data["image_file"] = open(self.image_filename, "rb")
        with TemporaryMySamples(self.sample_ids):
            if self.id:
                connection.open("results/{0}/edit/".format(self.id), data)
                logging.info("Edited result {0}.".format(self.id))
            else:
                self.id = connection.open("results/add/", data)
                logging.info("Added result {0}.".format(self.id))
        return self.id
