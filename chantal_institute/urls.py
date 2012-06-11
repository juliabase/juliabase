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
the Django application “chantal_institute”, which provides IEF-5-specific views for
all Chantal apps.  That's the reason why it must have a ``""`` URL pattern in
the root URL module.


:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/

"""

from __future__ import absolute_import, unicode_literals

from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns("chantal_institute.views.statistics",
                       (r"^about$", "about"),
                       (r"^statistics$", "statistics"),
                       )

urlpatterns += patterns("chantal_institute.views",
                        (r"^gc$", "group_meeting.meeting_schedule"),
                        (r"^pds_evaluation$", "pds_evaluation.evaluation"),
                        (r"^optical_data$", "optical_data_ermes.show"),
                        url(r"^plots/thumbnails/optical_data/(?P<filename>.+)", "optical_data_ermes.show_plot",
                           {"thumbnail": True}, "ermes_optical_plot_thumbnail"),
                        url(r"^plots/optical_data/(?P<filename>.+)", "optical_data_ermes.show_plot", {"thumbnail": False},
                           "ermes_optical_plot"),
                        )

urlpatterns += patterns("samples.views.lab_notebook",
                        url(r"^6-chamber_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "SixChamberDeposition"}, "export_lab_notebook_SixChamberDeposition"),
                        url(r"^6-chamber_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "SixChamberDeposition"}, "lab_notebook_SixChamberDeposition"),
                        url(r"^old_cluster_tool_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "OldClusterToolDeposition"},
                            "export_lab_notebook_OldClusterToolDeposition"),
                        url(r"^old_cluster_tool_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "OldClusterToolDeposition"}, "lab_notebook_OldClusterToolDeposition"),
                        url(r"^new_cluster_tool_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "NewClusterToolDeposition"},
                            "export_lab_notebook_NewClusterToolDeposition"),
                        url(r"^new_cluster_tool_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "NewClusterToolDeposition"}, "lab_notebook_NewClusterToolDeposition"),
                        url(r"^large-area_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "LargeAreaDeposition"}, "export_lab_notebook_LargeAreaDeposition"),
                        url(r"^large-area_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "LargeAreaDeposition"}, "lab_notebook_LargeAreaDeposition"),
                        url(r"^large_sputter_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "LargeSputterDeposition"},
                            "export_lab_notebook_LargeSputterDeposition"),
                        url(r"^large_sputter_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "LargeSputterDeposition"}, "lab_notebook_LargeSputterDeposition"),
                        url(r"^pds_measurements/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "PDSMeasurement"}, "export_lab_notebook_PDSMeasurement"),
                        url(r"^pds_measurements/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "PDSMeasurement"}, "lab_notebook_PDSMeasurement"),
                        url(r"^raman_measurements/1/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "RamanMeasurementOne"}, "export_lab_notebook_RamanMeasurementOne"),
                        url(r"^raman_measurements/1/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "RamanMeasurementOne"}, "lab_notebook_RamanMeasurementOne"),
                        url(r"^raman_measurements/2/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "RamanMeasurementTwo"}, "export_lab_notebook_RamanMeasurementTwo"),
                        url(r"^raman_measurements/2/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "RamanMeasurementTwo"}, "lab_notebook_RamanMeasurementTwo"),
                        url(r"^raman_measurements/3/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "RamanMeasurementThree"},
                            "export_lab_notebook_RamanMeasurementThree"),
                        url(r"^raman_measurements/3/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "RamanMeasurementThree"}, "lab_notebook_RamanMeasurementThree"),
                        url(r"^5-chamber_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "FiveChamberDeposition"}, "export_lab_notebook_FiveChamberDeposition"),
                        url(r"^5-chamber_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "FiveChamberDeposition"}, "lab_notebook_FiveChamberDeposition"),
                        url(r"^lada_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "LADADeposition"}, "export_lab_notebook_LADADeposition"),
                        url(r"^lada_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "LADADeposition"}, "lab_notebook_LADADeposition"),
                        url(r"^jana_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
                            "export", {"process_name": "JANADeposition"}, "export_lab_notebook_JANADeposition"),
                        url(r"^jana_depositions/lab_notebook/(?P<year_and_month>.*)",
                            "show", {"process_name": "JANADeposition"}, "lab_notebook_JANADeposition"),
                        )

urlpatterns += patterns("chantal_institute.views.samples",
                        (r"^samples/add/$", "sample.add"),
                        (r"^samples/(?P<sample_name>.+)-/copy_informal_stack/$", "sample.copy_informal_stack"),

                        url(r"^6-chamber_depositions/add/$", "six_chamber_deposition.edit",
                            {"deposition_number": None}, "add_6-chamber_deposition"),
                        url(r"^6-chamber_depositions/(?P<deposition_number>.+)/edit/$",
                            "six_chamber_deposition.edit", name="edit_6-chamber_deposition"),
                        (r"^6-chamber_depositions/(?P<deposition_number>.+)", "six_chamber_deposition.show"),

                        url(r"^large-area_depositions/add/$", "large_area_deposition.edit",
                            {"deposition_number": None}, "add_large-area_deposition"),
                        url(r"^large-area_depositions/(?P<deposition_number>.+)/edit/$",
                            "large_area_deposition.edit", name="edit_large-area_deposition"),
                        url(r"^large-area_depositions/(?P<deposition_number>.+)", "large_area_deposition.show"),

                        url(r"^old_cluster_tool_depositions/add/$", "old_cluster_tool_deposition.edit",
                            {"deposition_number": None}, "add_old_cluster_tool_deposition"),
                        url(r"^old_cluster_tool_depositions/(?P<deposition_number>.+)/edit/$",
                            "old_cluster_tool_deposition.edit", name="edit_old_cluster_tool_deposition"),
                        (r"^old_cluster_tool_depositions/(?P<deposition_number>.+)",
                         "old_cluster_tool_deposition.show"),

                        url(r"^new_cluster_tool_depositions/add/$", "new_cluster_tool_deposition.edit",
                            {"deposition_number": None}, "add_new_cluster_tool_deposition"),
                        url(r"^new_cluster_tool_depositions/(?P<deposition_number>.+)/edit/$",
                            "new_cluster_tool_deposition.edit", name="edit_new_cluster_tool_deposition"),
                        (r"^new_cluster_tool_depositions/(?P<deposition_number>.+)",
                         "new_cluster_tool_deposition.show"),

                        url(r"^pds_measurements/add/$", "pds_measurement.edit", {"pds_number": None}, "add_pds_measurement"),
                        url(r"^pds_measurements/(?P<pds_number>\d+)/edit/$", "pds_measurement.edit",
                            name="edit_pds_measurement"),
                        (r"^pds_measurements/(?P<pds_number>.+)", "pds_measurement.show"),

                        url(r"^5-chamber_depositions/add/$", "five_chamber_deposition.edit",
                            {"deposition_number": None}, "add_5-chamber_deposition"),
                        url(r"^5-chamber_depositions/(?P<deposition_number>.+)/edit/$",
                            "five_chamber_deposition.edit", name="edit_5-chamber_deposition"),
                        (r"^5-chamber_depositions/(?P<deposition_number>.+)", "five_chamber_deposition.show"),

                        url(r"^large_sputter_depositions/add/$", "large_sputter_deposition.edit",
                            {"deposition_number": None}, "add_large_sputter_deposition"),
                        url(r"^large_sputter_depositions/(?P<deposition_number>.+)/edit/$",
                            "large_sputter_deposition.edit", name="edit_large_sputter_deposition"),
                        (r"^large_sputter_depositions/(?P<deposition_number>.+)", "large_sputter_deposition.show"),

                        url(r"^dektak_measurements/add/$", "dektak_measurement.edit", {"dektak_number": None},
                            "add_dektak_measurement"),
                        url(r"^dektak_measurements/(?P<dektak_number>\d+)/edit/$", "dektak_measurement.edit",
                            name="edit_dektak_measurement"),

                        url(r"^luma_measurements/add/$", "luma_measurement.edit", {"process_id": None},
                            "add_luma_measurement"),
                        url(r"^luma_measurements/(?P<process_id>\d+)/edit/$", "luma_measurement.edit",
                            name="edit_luma_measurement"),

                        url(r"^conductivity_measurements/add/$", "conductivity_measurement.edit",
                            {"conductivity_set_pk": None}, "add_conductivity_measurement"),
                        url(r"^conductivity_measurements/(?P<conductivity_set_pk>\d+)/edit/$",
                            "conductivity_measurement.edit", name="edit_conductivity_measurement"),
                        (r"^conductivity_measurements/(?P<apparatus>conductivity[0-2])/(?P<sample_id>.+)",
                         "json_client.get_current_conductivity_measurement_set"),

                        url(r"^raman_measurements/(?P<apparatus_number>[123])/add/$", "raman_measurement.edit",
                            {"raman_number": None}, "add_raman_measurement"),
                        url(r"^raman_measurements/(?P<apparatus_number>[123])/(?P<raman_number>.+)/edit/$",
                            "raman_measurement.edit", name="edit_raman_measurement"),
                        (r"^raman_measurements/(?P<apparatus_number>[123])/(?P<raman_number>.+)", "raman_measurement.show"),

                        url(r"^manual_etching/add/$", "manual_etching.edit", {"etching_number": None},
                            "add_manual_etching"),
                        url(r"^manual_etching/(?P<etching_number>.+)/edit/$", "manual_etching.edit",
                            name="edit_manual_etching"),

                        url(r"^throughput_etching/add/$", "throughput_etching.edit", {"etching_number": None},
                            "add_throughput_etching"),
                        url(r"^throughput_etching/(?P<etching_number>.+)/edit/$", "throughput_etching.edit",
                            name="edit_throughput_etching"),

                        url(r"^p_hot_wire_depositions/add/$", "p_hot_wire_deposition.edit",
                            {"deposition_number": None}, "add_p_hot_wire_deposition"),
                        url(r"^p_hot_wire_depositions/(?P<deposition_number>.+)/edit/$",
                            "p_hot_wire_deposition.edit", name="edit_p_hot_wire_deposition"),
                        (r"^p_hot_wire_depositions/(?P<deposition_number>.+)",
                         "p_hot_wire_deposition.show"),

                        url(r"^dsr_measurements/add/$", "dsr_measurement.edit", {"process_id": None}, "add_dsr_measurement"),
                        url(r"^dsr_measurements/(?P<process_id>\d+)/edit/$", "dsr_measurement.edit",
                            name="edit_dsr_measurement"),
                        url(r"^dsr_measurements/(?P<process_id>\d+)$", "dsr_measurement.show",
                            name="show_dsr_measurement"),

                        url(r"^ir_measurements/add/$", "ir_measurement.edit", {"ir_number": None}, "add_ir_measurement"),
                        url(r"^ir_measurements/(?P<ir_number>.+)/edit/$", "ir_measurement.edit",
                            name="edit_ir_measurement"),

                        url(r"^substrates/add/$", "substrate.edit", {"substrate_id": None}, "add_substrate"),
                        url(r"^substrates/(?P<substrate_id>.+)/edit/$", "substrate.edit",
                            name="edit_substrate"),

                        url(r"^cleaning_process/add/$", "cleaning_process.edit", {"cleaning_process_id": None},
                            "add_cleaning_process"),
                        url(r"^cleaning_process/(?P<cleaning_process_id>.+)/edit/$", "cleaning_process.edit",
                            name="edit_cleaning_process"),

                        url(r"^solarsimulator_measurements/photo/add/$", "solarsimulator_photo_measurement.edit",
                            {"process_id": None}, "add_solarsimulator_photo_measurement"),
                        url(r"^solarsimulator_measurements/photo/(?P<process_id>\d+)/edit/$",
                            "solarsimulator_photo_measurement.edit", name="edit_solarsimulator_photo_measurement"),
                        url(r"solarsimulator_measurements/photo/(?P<process_id>\d+)$",
                            "solarsimulator_photo_measurement.show", name="show_solarsimulator_photo_measurement"),

                        url(r"^solarsimulator_measurements/dark/add/$", "solarsimulator_dark_measurement.edit",
                            {"process_id": None}, "add_solarsimulator_dark_measurement"),
                        url(r"^solarsimulator_measurements/dark/(?P<process_id>\d+)/edit/$",
                            "solarsimulator_dark_measurement.edit", name="edit_solarsimulator_dark_measurement"),
                        url(r"solarsimulator_measurements/dark/(?P<process_id>\d+)$",
                            "solarsimulator_dark_measurement.show", name="show_solarsimulator_dark_measurement"),

                        url(r"^structuring_process/add/$", "structuring.edit", {"process_id": None},
                            "add_sructuring_process"),
                        url(r"^structuring_process/(?P<process_id>.+)/edit/$", "structuring.edit",
                            name="edit_structuring_process"),

                        (r"^substrates_by_sample/(?P<sample_id>.+)", "json_client.substrate_by_sample"),
                        (r"^raman_measurements/file_path", "json_client.raman_file_path"),
                        (r"^raman_measurements/by_filepath/(?P<filepath>.+)", "json_client.raman_by_filepath"),

                        (r"^solarsimulator_measurements/by_filepath", "json_client.get_maike_by_filepath"),
                        (r"^structurings/by_sample/(?P<sample_id>.+)", "json_client.get_current_structuring"),
                        (r"^solarsimulator_measurements/matching/(?P<irradiance>[A-Za-z0-9.]+)/(?P<sample_id>\d+)/"
                         r"(?P<cell_position>[^/]+)/(?P<date>\d{4}-\d\d-\d\d)/",
                         "json_client.get_matching_solarsimulator_measurement"),

                        url(r"^dsr_measurements/by_filepath/", "json_client.get_dsr_by_filepath"),

                        url(r"^old_evaporation/add/$", "small_evaporation.edit", {"process_number": None},
                            "add_small_evaporation"),
                        url(r"^small_evaporation/(?P<process_number>.+)/edit/$", "small_evaporation.edit",
                            name="edit_small_evaporation"),

                        url(r"^large_evaporation/add/$", "large_evaporation.edit", {"process_number": None},
                            "add_large_evaporation"),
                        url(r"^large_evaporation/(?P<process_number>.+)/edit/$", "large_evaporation.edit",
                            name="edit_large_evaporation"),

                        url(r"^layer_thickness/add/$", "layer_thickness.edit", {"process_id": None}, "add_layer_thickness"),
                        url(r"^layer_thickness/(?P<process_id>.+)/edit/$", "layer_thickness.edit",
                            name="edit_layer_thickness"),

                        url(r"^sputter_characterizations/add/$", "sputter_characterization.edit", {"process_id": None},
                            "add_sputter_characterization"),
                        url(r"^sputter_characterizations/(?P<process_id>.+)/edit/$", "sputter_characterization.edit",
                            name="edit_sputter_characterization"),

                        url(r"^zno_characterizations/add/$", "zno_characterization.add", None, "add_zno_characterization"),

                        (r"^claims/(?P<username>.+)/add_oldstyle/$", "claim.add_oldstyle"),

                        url(r"^stacks/(?P<sample_id>\d+)", "stack.show_stack", {"thumbnail": False}, "stack_diagram"),
                        url(r"^stacks/thumbnails/(?P<sample_id>\d+)", "stack.show_stack", {"thumbnail": True},
                            "stack_diagram_thumbnail"),

                        url(r"layouts/(?P<sample_id>\d+)/(?P<process_id>\d+)", "layout.show_layout"),

                        (r"^printer_label/(?P<sample_id>\d+)$", "sample.printer_label"),

                        url(r"^lada_depositions/add/$", "lada_deposition.edit",
                            {"deposition_number": None}, "add_lada_deposition"),
                        url(r"^lada_depositions/(?P<deposition_number>.+)/edit/$",
                            "lada_deposition.edit", name="edit_lada_deposition"),
                        url(r"^lada_depositions/(?P<deposition_number>.+)", "lada_deposition.show"),

                        url(r"^large_area_cleaning_process/add/$", "large_area_cleaning_process.edit",
                            {"large_area_cleaning_process_id": None}, "add_large_area_cleaning_process"),
                        url(r"^large_area_cleaning_process/(?P<large_area_cleaning_process_id>.+)/edit/$",
                            "large_area_cleaning_process.edit", name="edit_large_area_cleaning_process"),

                        url(r"^jana_depositions/add/$", "jana_deposition.edit",
                            {"deposition_number": None}, "add_jana_deposition"),
                        url(r"^jana_depositions/(?P<deposition_number>.+)/edit/$",
                            "jana_deposition.edit", name="edit_jana_deposition"),
                        url(r"^jana_depositions/(?P<deposition_number>.+)", "jana_deposition.show"),
                        )
