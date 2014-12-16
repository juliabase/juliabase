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

from django.conf.urls import url
from samples.url_utils import PatternGenerator


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
