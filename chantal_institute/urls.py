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


"""Mapping URL patterns to function calls.  This is the local URL dispatch of
the Django application “chantal_institute”, which provides institute-specific views for
all Chantal apps.  That's the reason why it must have a ``""`` URL pattern in
the root URL module.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls import url, patterns


urlpatterns = patterns("samples.views.lab_notebook",
                        url(r"^5-chamber_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "FiveChamberDeposition"}, "export_lab_notebook_FiveChamberDeposition"),
                        url(r"^5-chamber_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "FiveChamberDeposition"}, "lab_notebook_FiveChamberDeposition"),
                        )

urlpatterns += patterns("chantal_institute.views.samples",
                        (r"^samples/add/$", "sample.add"),
                        (r"^samples/(?P<sample_name>.+)-/copy_informal_stack/$", "sample.copy_informal_stack"),

                        url(r"^cluster_tool_depositions/add/$", "cluster_tool_deposition.edit",
                            {"deposition_number": None}, "add_cluster_tool_deposition"),
                        url(r"^cluster_tool_depositions/(?P<deposition_number>.+)/edit/$",
                            "cluster_tool_deposition.edit", name="edit_cluster_tool_deposition"),
                        (r"^cluster_tool_depositions/(?P<deposition_number>.+)",
                         "cluster_tool_deposition.show"),

                        url(r"^pds_measurements/add/$", "pds_measurement.edit", {"pds_number": None}, "add_pds_measurement"),
                        url(r"^pds_measurements/(?P<pds_number>\d+)/edit/$", "pds_measurement.edit",
                            name="edit_pds_measurement"),
                        (r"^pds_measurements/(?P<pds_number>.+)", "pds_measurement.show"),

                        url(r"^5-chamber_depositions/add/$", "five_chamber_deposition.edit",
                            {"deposition_number": None}, "add_5-chamber_deposition"),
                        url(r"^5-chamber_depositions/(?P<deposition_number>.+)/edit/$",
                            "five_chamber_deposition.edit", name="edit_5-chamber_deposition"),
                        (r"^5-chamber_depositions/(?P<deposition_number>.+)", "five_chamber_deposition.show"),

                        url(r"^substrates/add/$", "substrate.edit", {"substrate_id": None}, "add_substrate"),
                        url(r"^substrates/(?P<substrate_id>.+)/edit/$", "substrate.edit",
                            name="edit_substrate"),

                        url(r"^solarsimulator_measurements/photo/add/$", "solarsimulator_photo_measurement.edit",
                            {"process_id": None}, "add_solarsimulator_photo_measurement"),
                        url(r"^solarsimulator_measurements/photo/(?P<process_id>\d+)/edit/$",
                            "solarsimulator_photo_measurement.edit", name="edit_solarsimulator_photo_measurement"),
                        url(r"solarsimulator_measurements/photo/(?P<process_id>\d+)$",
                            "solarsimulator_photo_measurement.show", name="show_solarsimulator_photo_measurement"),

                        url(r"^structuring_process/add/$", "structuring.edit", {"process_id": None},
                            "add_sructuring_process"),
                        url(r"^structuring_process/(?P<process_id>.+)/edit/$", "structuring.edit",
                            name="edit_structuring_process"),

                        (r"^substrates_by_sample/(?P<sample_id>.+)", "json_client.substrate_by_sample"),

                        (r"^solarsimulator_measurements/by_filepath", "json_client.get_maike_by_filepath"),
                        (r"^structurings/by_sample/(?P<sample_id>.+)", "json_client.get_current_structuring"),
                        (r"^solarsimulator_measurements/matching/(?P<irradiance>[A-Za-z0-9.]+)/(?P<sample_id>\d+)/"
                         r"(?P<cell_position>[^/]+)/(?P<date>\d{4}-\d\d-\d\d)/",
                         "json_client.get_matching_solarsimulator_measurement"),

                        (r"^claims/(?P<username>.+)/add_oldstyle/$", "claim.add_oldstyle"),

                        url(r"^stacks/(?P<sample_id>\d+)", "stack.show_stack", {"thumbnail": False}, "stack_diagram"),
                        url(r"^stacks/thumbnails/(?P<sample_id>\d+)", "stack.show_stack", {"thumbnail": True},
                            "stack_diagram_thumbnail"),

                        url(r"layouts/(?P<sample_id>\d+)/(?P<process_id>\d+)", "layout.show_layout"),

                        (r"^printer_label/(?P<sample_id>\d+)$", "sample.printer_label"),

                        )
