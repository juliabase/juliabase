# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
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

from django.urls import re_path
from django.views.generic import TemplateView
from samples.utils.urls import PatternGenerator
from institute.views.samples import sample, claim, stack, layout, json_client, substrate, structuring, my_layers


app_name = "institute"

urlpatterns = [
    # General additions

    re_path(r"^samples/add/$", sample.add, name="add_samples"),
    re_path(r"^samples/(?P<sample_name>.+)/copy_informal_stack/$", sample.copy_informal_stack, name="copy_informal_stack"),
    re_path(r"^claims/(?P<username>.+)/add_oldstyle/$", claim.add_oldstyle, name="add_claim_oldstyle"),
    re_path(r"^my_layers/(?P<login_name>.+)", my_layers.edit, name="edit_my_layers"),
    re_path(r"^stacks/(?P<sample_id>\d+)$", stack.show_stack, {"thumbnail": False}, "stack_diagram"),
    re_path(r"^stacks/thumbnails/(?P<sample_id>\d+)$", stack.show_stack, {"thumbnail": True},
            "stack_diagram_thumbnail"),
    re_path(r"layouts/(?P<sample_id>\d+)/(?P<process_id>\d+)$", layout.show_layout, name="show_layout"),
    re_path(r"^printer_label/(?P<sample_id>\d+)$", sample.printer_label, name="printer_label"),
    re_path(r"^trac/", TemplateView.as_view(template_name="bug_tracker.html")),

    # Remote client

    re_path(r"^substrates_by_sample/(?P<sample_id>\d+)$", json_client.substrate_by_sample),
    re_path(r"^next_deposition_number/(?P<letter>.+)", json_client.next_deposition_number),
    re_path(r"^solarsimulator_measurements/by_filepath",
            json_client.get_solarsimulator_measurement_by_filepath),
    re_path(r"^structurings/by_sample/(?P<sample_id>\d+)$", json_client.get_current_structuring),
    re_path(r"^solarsimulator_measurements/matching/(?P<irradiation>[A-Za-z0-9.]+)/(?P<sample_id>\d+)/"
            r"(?P<cell_position>[^/]+)/(?P<date>\d{4}-\d\d-\d\d)/$",
            json_client.get_matching_solarsimulator_measurement),
    # I don't add the following two with the pattern generator in order to
    # prevent an “add” link on the main menu page; they are used only by the
    # remote client.
    re_path(r"^substrates/add/$", substrate.EditView.as_view(), {"substrate_id": None}),
    re_path(r"^structurings/add/$", structuring.EditView.as_view(), {"structuring_id": None}),
]


# Physical processes

pattern_generator = PatternGenerator(urlpatterns, "institute.views.samples")
pattern_generator.deposition("ClusterToolDeposition", views={"add", "edit"})
pattern_generator.deposition("FiveChamberDeposition", "5-chamber_depositions")
pattern_generator.physical_process("PDSMeasurement")
pattern_generator.physical_process("Substrate", views={"edit"})
pattern_generator.physical_process("Structuring", views={"edit"})
pattern_generator.physical_process("SolarsimulatorMeasurement")
pattern_generator.physical_process("LayerThicknessMeasurement")
