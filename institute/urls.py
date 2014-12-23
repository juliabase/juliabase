#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


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


urlpatterns = [
    # General additions

    url(r"^samples/add/$", "institute.views.samples.sample.add"),
    url(r"^samples/(?P<sample_name>.+)/copy_informal_stack/$", "institute.views.samples.sample.copy_informal_stack"),
    url(r"^claims/(?P<username>.+)/add_oldstyle/$", "institute.views.samples.claim.add_oldstyle"),
    url(r"^stacks/(?P<sample_id>\d+)$", "institute.views.samples.stack.show_stack", {"thumbnail": False}, "stack_diagram"),
    url(r"^stacks/thumbnails/(?P<sample_id>\d+)$", "institute.views.samples.stack.show_stack", {"thumbnail": True},
        "stack_diagram_thumbnail"),
    url(r"layouts/(?P<sample_id>\d+)/(?P<process_id>\d+)$", "institute.views.samples.layout.show_layout"),
    url(r"^printer_label/(?P<sample_id>\d+)$", "institute.views.samples.sample.printer_label"),
    url(r"^trac/", TemplateView.as_view(template_name="bug_tracker.html")),

    # Remote client

    url(r"^substrates_by_sample/(?P<sample_id>\d+)$", "institute.views.samples.json_client.substrate_by_sample"),
    url(r"^next_deposition_number/(?P<letter>.+)", "institute.views.samples.json_client.next_deposition_number"),
    url(r"^solarsimulator_measurements/by_filepath",
        "institute.views.samples.json_client.get_solarsimulator_measurement_by_filepath"),
    url(r"^structurings/by_sample/(?P<sample_id>\d+)$", "institute.views.samples.json_client.get_current_structuring"),
    url(r"^solarsimulator_measurements/matching/(?P<irradiation>[A-Za-z0-9.]+)/(?P<sample_id>\d+)/"
        r"(?P<cell_position>[^/]+)/(?P<date>\d{4}-\d\d-\d\d)/$",
        "institute.views.samples.json_client.get_matching_solarsimulator_measurement"),
    # I don't add the following two with the pattern generator in order to
    # prevent an “add” link on the main menu page; they are used only by the
    # remote client.
    url(r"^substrates/add/$", "institute.views.samples.substrate.edit", {"substrate_id": None}),
    url(r"^structurings/add/$", "institute.views.samples.structuring.edit", {"structuring_id": None}),
]


# Physical processes

pattern_generator = PatternGenerator(urlpatterns, "institute.views.samples")
pattern_generator.deposition("ClusterToolDeposition", views={"add", "edit"})
pattern_generator.deposition("FiveChamberDeposition", "5-chamber_depositions")
pattern_generator.physical_process("PDSMeasurement", "number")
pattern_generator.physical_process("Substrate", views={"edit"})
pattern_generator.physical_process("Structuring", views={"edit"})
pattern_generator.physical_process("SolarsimulatorMeasurement")
pattern_generator.physical_process("LayerThicknessMeasurement")
