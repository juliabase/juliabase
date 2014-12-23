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


"""Views to add and edit substrates.
"""

from __future__ import unicode_literals
import datetime
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.contrib.auth.decorators import login_required
from institute import models as institute_models
from samples import permissions
import samples.utils.views as utils


class SubstrateForm(utils.ProcessForm):
    """Model form class for a substrate.
    """
    class Meta:
        model = institute_models.Substrate
        fields = "__all__"

    def clean(self):
        _ = ugettext
        cleaned_data = super(SubstrateForm, self).clean()
        if cleaned_data.get("material") == "custom" and not cleaned_data.get("comments"):
            self.add_error("comments", _("For a custom substrate, you must give substrate comments."))
        return cleaned_data


def is_referentially_valid(substrate_form, samples_form, edit_description_form):
    """Test whether all forms are consistent with each other and with the
    database.  For example, no sample must get more than one substrate.

    :param substrate_form: form with the substrate core data
    :param samples_form: form with the sample selection
    :param edit_description_form: form with the description of the changes

    :type substrate_form: `SubstrateForm`
    :type samples_form: `samples.utils.views.DepositionSamplesForm`
    :type edit_description_form: `samples.utils.views.EditDescriptionForm`
        or NoneType

    :return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if samples_form.is_valid() and substrate_form.is_valid() and samples_form.is_bound:
        for sample in samples_form.cleaned_data["sample_list"]:
            processes = list(sample.processes.all())
            if processes:
                earliest_timestamp = min(process.timestamp for process in processes)
                if earliest_timestamp < substrate_form.cleaned_data["timestamp"]:
                    samples_form.add_error("sample_list",
                                           _("Sample {0} has already processes before the timestamp of this substrate, "
                                           "namely from {1}.").format(sample, earliest_timestamp))
                for process in processes:
                    if process.content_type.model_class() == institute_models.Substrate:
                        samples_form.add_error("sample_list", _("Sample {0} has already a substrate.").format(sample))
                        referentially_valid = False
                        break
    return referentially_valid


@login_required
def edit(request, substrate_id):
    """Central view for editing and creating substrates.  If ``substrate_id`` is
    ``None``, a new substrate is created.

    :param request: the HTTP request object
    :param substrate_id: the id of the subtrate

    :type request: QueryDict
    :type deposition_number: unicode or NoneType

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    substrate = get_object_or_404(institute_models.Substrate, pk=utils.convert_id_to_int(substrate_id)) if substrate_id else None
    permissions.assert_can_add_edit_physical_process(request.user, substrate, institute_models.Substrate)
    preset_sample = utils.extract_preset_sample(request) if not substrate else None
    if request.method == "POST":
        substrate_form = SubstrateForm(request.user, request.POST, instance=substrate)
        samples_form = utils.DepositionSamplesForm(request.user, preset_sample, substrate, request.POST)
        edit_description_form = utils.EditDescriptionForm(request.POST) if substrate else None
        referentially_valid = is_referentially_valid(substrate_form, samples_form, edit_description_form)
        if all([substrate_form.is_valid(), samples_form.is_valid() or not samples_form.is_bound,
                edit_description_form.is_valid() if edit_description_form else True]) and referentially_valid:
            new_substrate = substrate_form.save()
            if samples_form.is_bound:
                new_substrate.samples = samples_form.cleaned_data["sample_list"]
            utils.Reporter(request.user).report_physical_process(
                new_substrate, edit_description_form.cleaned_data if edit_description_form else None)
            if substrate:
                return utils.successful_response(
                    request, _("Substrate {0} was successfully changed in the database.").format(new_substrate))
            else:
                return utils.successful_response(
                    request, _("Substrate {0} was successfully added to the database.").format(new_substrate),
                    json_response=new_substrate.pk)
    else:
        substrate_form = SubstrateForm(request.user, instance=substrate)
        samples_form = utils.DepositionSamplesForm(request.user, preset_sample, substrate)
        edit_description_form = utils.EditDescriptionForm() if substrate else None
    title = _("Edit substrate “{0}”").format(substrate) if substrate else _("Add substrate")
    return render(request, "samples/edit_substrate.html", {"title": title, "substrate": substrate_form,
                                                           "samples": samples_form,
                                                           "edit_description": edit_description_form})
