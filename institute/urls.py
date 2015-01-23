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
the Django application “institute”, which provides institute-specific views for all
JuliaBase apps.  That's the reason why it must have a ``""`` URL pattern in the
root URL module.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/
"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url
from django.views.generic import TemplateView
from samples.utils.urls import PatternGenerator
from institute.views.samples import sample, claim, stack, layout, json_client, substrate, structuring
from institute.views.samples.pds_measurement import PDSMeasurementView


urlpatterns = [
    # General additions

    url(r"^samples/add/$", sample.add),
    url(r"^samples/(?P<sample_name>.+)/copy_informal_stack/$", sample.copy_informal_stack),
    url(r"^claims/(?P<username>.+)/add_oldstyle/$", claim.add_oldstyle),
    url(r"^stacks/(?P<sample_id>\d+)$", stack.show_stack, {"thumbnail": False}, "stack_diagram"),
    url(r"^stacks/thumbnails/(?P<sample_id>\d+)$", stack.show_stack, {"thumbnail": True},
        "stack_diagram_thumbnail"),
    url(r"layouts/(?P<sample_id>\d+)/(?P<process_id>\d+)$", layout.show_layout),
    url(r"^printer_label/(?P<sample_id>\d+)$", sample.printer_label),
    url(r"^trac/", TemplateView.as_view(template_name="bug_tracker.html")),

    # Remote client

    url(r"^substrates_by_sample/(?P<sample_id>\d+)$", json_client.substrate_by_sample),
    url(r"^next_deposition_number/(?P<letter>.+)", json_client.next_deposition_number),
    url(r"^solarsimulator_measurements/by_filepath",
        json_client.get_solarsimulator_measurement_by_filepath),
    url(r"^structurings/by_sample/(?P<sample_id>\d+)$", json_client.get_current_structuring),
    url(r"^solarsimulator_measurements/matching/(?P<irradiation>[A-Za-z0-9.]+)/(?P<sample_id>\d+)/"
        r"(?P<cell_position>[^/]+)/(?P<date>\d{4}-\d\d-\d\d)/$",
        json_client.get_matching_solarsimulator_measurement),
    # I don't add the following two with the pattern generator in order to
    # prevent an “add” link on the main menu page; they are used only by the
    # remote client.
    url(r"^substrates/add/$", substrate.edit, {"substrate_id": None}),
    url(r"^structurings/add/$", structuring.edit, {"structuring_id": None}),
    url(r"^pds_measurements/add/$", PDSMeasurementView.as_view(), {"number": None}),
    url(r"^pds_measurements/(?P<number>.+)/edit/$", PDSMeasurementView.as_view()),
]


# Physical processes

pattern_generator = PatternGenerator(urlpatterns, "institute.views.samples")
pattern_generator.deposition("ClusterToolDeposition", views={"add", "edit"})
pattern_generator.deposition("FiveChamberDeposition", "5-chamber_depositions")
#pattern_generator.physical_process("PDSMeasurement", "number")
pattern_generator.physical_process("Substrate", views={"edit"})
pattern_generator.physical_process("Structuring", views={"edit"})
pattern_generator.physical_process("SolarsimulatorMeasurement")
#pattern_generator.physical_process("LayerThicknessMeasurement")
