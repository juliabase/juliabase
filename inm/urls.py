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


"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “inm”, which provides institute-specific views for all
JuliaBase apps.  That's the reason why it must have a ``""`` URL pattern in the
root URL module.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url, patterns
from samples.views.shared_utils import camel_case_to_underscores


class PatternGenerator(object):

    def __init__(self, url_patterns, views_prefix):
        self.views_prefix = views_prefix + "."
        self.url_patterns = url_patterns

    def physical_process(self, class_name, identifying_field=None, url_name=None, views={"add", "edit"}):
        camel_case_class_name = camel_case_to_underscores(class_name)
        url_name = url_name or camel_case_class_name + "s"
        assert not views - {"add", "edit", "show", "lab_notebook"}
        normalized_id_field = identifying_field or camel_case_class_name + "_id"
        if "add" in views:
            self.url_patterns.append(url(r"^{}/add/$".format(url_name), self.views_prefix + camel_case_class_name + ".edit",
                                         {normalized_id_field: None}, "add_" + camel_case_class_name))
        if "edit" in views:
            self.url_patterns.append(url(r"^{}/(?P<{}>.+)/edit/$".format(url_name, normalized_id_field),
                                         self.views_prefix + camel_case_class_name + ".edit", name="edit_" +
                                         camel_case_class_name))
        if "show" in views:
            self.url_patterns.append(url(r"^{}/(?P<{}>.+)".format(url_name, normalized_id_field),
                                         self.views_prefix + camel_case_class_name + ".show", name="show_" +
                                         camel_case_class_name))
        else:
            self.url_patterns.append(url(r"^{}/(?P<process_id>.+)".format(url_name, normalized_id_field),
                                         "samples.views.main.show_process", {"process_name": class_name},
                                         name="show_" + camel_case_class_name))
        if "lab_notebook" in views:
            self.url_patterns.extend([url(r"^{}/lab_notebook/(?P<year_and_month>.*)/export/".format(url_name),
                                          "samples.views.lab_notebook.export", {"process_name": class_name},
                                          "export_lab_notebook_" + camel_case_class_name),
                                      url(r"^{}/lab_notebook/(?P<year_and_month>.*)".format(url_name),
                                          "samples.views.lab_notebook.show", {"process_name": class_name},
                                          "lab_notebook_" + camel_case_class_name)])


urlpatterns = []

pattern_generator = PatternGenerator(urlpatterns, "inm.views.samples")
pattern_generator.physical_process("ClusterToolDeposition", "number")
pattern_generator.physical_process("FiveChamberDeposition", "number", "5-chamber_depositions",
                                   {"add", "edit", "lab_notebook"})
pattern_generator.physical_process("PDSMeasurement", "number")
pattern_generator.physical_process("Substrate", views={"edit"})
pattern_generator.physical_process("Structuring", views={"edit"})
pattern_generator.physical_process("SolarsimulatorMeasurement")


urlpatterns += [
    url(r"^samples/add/$", "inm.views.samples.sample.add"),
    url(r"^samples/(?P<sample_name>.+)-/copy_informal_stack/$", "inm.views.samples.sample.copy_informal_stack"),

    url(r"^add_sample$", "inm.views.samples.json_client.add_sample"),
    url(r"^substrates_by_sample/(?P<sample_id>.+)", "inm.views.samples.json_client.substrate_by_sample"),
    url(r"^next_deposition_number/(?P<letter>.+)", "inm.views.samples.json_client.next_deposition_number"),
    url(r"^solarsimulator_measurements/by_filepath", "inm.views.samples.json_client.get_maike_by_filepath"),
    url(r"^structurings/by_sample/(?P<sample_id>.+)", "inm.views.samples.json_client.get_current_structuring"),
    url(r"^solarsimulator_measurements/matching/(?P<irradiation>[A-Za-z0-9.]+)/(?P<sample_id>\d+)/"
        r"(?P<cell_position>[^/]+)/(?P<date>\d{4}-\d\d-\d\d)/",
        "inm.views.samples.json_client.get_matching_solarsimulator_measurement"),

    url(r"^claims/(?P<username>.+)/add_oldstyle/$", "inm.views.samples.claim.add_oldstyle"),

    url(r"^stacks/(?P<sample_id>\d+)", "inm.views.samples.stack.show_stack", {"thumbnail": False}, "stack_diagram"),
    url(r"^stacks/thumbnails/(?P<sample_id>\d+)", "inm.views.samples.stack.show_stack", {"thumbnail": True},
        "stack_diagram_thumbnail"),

    url(r"layouts/(?P<sample_id>\d+)/(?P<process_id>\d+)", "inm.views.samples.layout.show_layout"),

    url(r"^printer_label/(?P<sample_id>\d+)$", "inm.views.samples.sample.printer_label"),
]
