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


"""Helper classes and function for the views that are used for the ipv institude.
It extends the samples.views.form_utils with institute specific classes and functions.
"""

from __future__ import absolute_import, unicode_literals

import urllib
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.translation import ugettext as _
import django.core.urlresolvers
from django.contrib import messages
from samples.views import utils
from samples.views.form_utils import *
from samples.views import sample
from chantal_common.utils import append_error, is_json_requested, respond_in_json
from django.utils.text import capfirst


def edit_depositions(request, deposition_number, form_set, institute_model, edit_url, rename_conservatively=False):
    """This function is the central view for editing, creating, and duplicating for any deposition.
    The edit functions in the deposition views are wrapper functions who provides this function
    with the specific informations.
    If ``deposition_number`` is ``None``, a new depositon is
    created (possibly by duplicating another one).

    :Parameters:
      - `request`: the HTTP request object
      - `deposition_number`: the number (=name) or the deposition
      - `form_set`: the related formset object for the deposition
      - `institute_model`: the related Database model
      - `edit_url`: the location of the edit template
      - `rename_conservatively`: If ``True``, rename only provisional and
        cleaning process names.  This is used by the Large Sputter deposition.
        See the ``new_names`` parameter in
        `samples.views.split_after_deposition.forms_from_database` for how this
        is achieved

    :type request: ``QueryDict``
    :type deposition_number: unicode or ``NoneType``
    :type form_set: ``FormSet`` object
    :type institute_model: ``samples.models_depositions.Deposition``
    :type edit_url: unicode
    :type rename_conservatively: bool

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    permissions.assert_can_add_edit_physical_process(request.user, form_set.deposition, institute_model)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        deposition = form_set.save_to_database()
        if deposition:
            if form_set.remove_from_my_samples_form and \
                    form_set.remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), form_set.user)
            next_view = next_view_kwargs = None
            query_string = ""
            newly_finished = deposition.finished and (not form_set.deposition or getattr(form_set, "unfinished", False))
            if newly_finished:
                rename = False
                new_names = {}
                if rename_conservatively:
                    for sample in deposition.samples.all():
                        name_format = utils.sample_name_format(sample.name)
                        if name_format == "provisional" or name_format == "old" and sample.name[2] in ["N", "V"]:
                            new_names[sample.id] = "{0}-{1}".format(deposition.number, len(new_names) + 1)
                            rename = True
                        elif name_format == "old":
                            new_names[sample.id] = sample.name
                else:
                    rename = True
                if rename:
                    next_view = "samples.views.split_after_deposition.split_and_rename_after_deposition"
                    next_view_kwargs = {"deposition_number": deposition.number}
                    query_string = urllib.urlencode([("new-name-{0}".format(id_), new_name)
                                                     for id_, new_name in new_names.iteritems()])
            elif not deposition.finished:
                next_view, __, next_view_kwargs = django.core.urlresolvers.resolve(request.path)
                next_view_kwargs["deposition_number"] = deposition.number
            if deposition_number:
                message = _("Deposition {number} was successfully changed in the database."). \
                    format(number=deposition.number)
                json_response = True
            else:
                message = _("Deposition {number} was successfully added to the database.").format(number=deposition.number)
                json_response = deposition.number
            return utils.successful_response(request, message, next_view, next_view_kwargs or {}, query_string,
                                             forced=next_view is not None, json_response=json_response)
        else:
            messages.error(request, _("The deposition was not saved due to incorrect or missing data."))
    else:
        form_set.from_database(utils.parse_query_string(request))
    institute_model_name = utils.capitalize_first_letter(institute_model._meta.verbose_name)
    title = _("Edit {name} “{number}”").format(name=institute_model_name, number=deposition_number) if deposition_number \
        else _("Add {name}").format(name=institute_model._meta.verbose_name)
    title = utils.capitalize_first_letter(title)
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render_to_response(edit_url, context_dict, context_instance=RequestContext(request))


def show_depositions(request, deposition_number, institute_model):
    """Show an existing new deposision.  You must be an operator of the deposition
    *or* be able to view one of the samples
    affected by this deposition in order to be allowed to view it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number (=name) or the deposition
      - `institute_model`: the related Database model

    :type request: ``HttpRequest``
    :type deposition_number: unicode
    :type institute_model: ``samples.models_depositions.Deposition``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    deposition = get_object_or_404(institute_model, number=deposition_number)
    permissions.assert_can_view_physical_process(request.user, deposition)
    if is_json_requested(request):
        return respond_in_json(deposition.get_data().to_dict())
    template_context = {"title": _("{name} “{number}”").format(name=institute_model._meta.verbose_name, number=deposition.number),
                        "samples": deposition.samples.all(),
                        "process": deposition}
    template_context.update(utils.digest_process(deposition, request.user))
    return render_to_response("samples/show_process.html", template_context, context_instance=RequestContext(request))


def measurement_is_referentially_valid(measurement_form, sample_form, measurement_number, institute_model):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `measurement_form`: a bound measurement form
      - `sample_form`: a bound sample selection form
      - `measurement_number`: The number of the measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.
      - `institute_model`: the related Database model

    :type measurement_form: `form_utils.ProcessForm`
    :type sample_form: `SampleForm`
    :type measurement_number: unicode
    :type institute_model: ``samples.models_physical_processes.Process``

    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if measurement_form.is_valid():
        number = measurement_form.cleaned_data.get("number")
        number = number and unicode(number)
        if number is not None and (measurement_number is None or number != measurement_number) and \
                institute_model.objects.filter(number=number).exists():
            append_error(measurement_form, _("This number is already in use."), "number")
            referentially_valid = False
        if sample_form.is_valid() and dead_samples([sample_form.cleaned_data["sample"]],
                                                    measurement_form.cleaned_data["timestamp"]):
            append_error(measurement_form, _("Sample is already dead at this time."), "timestamp")
            referentially_valid = False
    else:
        referentially_valid = False
    return referentially_valid


def three_digits(number):
    """
    :Parameters:
      - `number`: the number of the deposition (only the number after the
        deposition system letter)

    :type number: int

    :Return:
      The number filled with leading zeros so that it has at least three
      digits.

    :rtype: unicode
    """
    return "{0:03}".format(number)


class SampleForm(forms.Form):
    """Form for the sample selection field.  You can only select *one* sample
    per process (in contrast to depositions).
    """
    _ = ugettext_lazy
    sample = SampleField(label=capfirst(_("sample")))

    def __init__(self, user, process_instance, preset_sample, *args, **kwargs):
        """Form constructor.  I only set the selection of samples to the
        current user's “My Samples”.

        :Parameters:
          - `user`: the current user
          - `process_instance`: the process instance to be edited, or ``None`` if
            a new is about to be created
          - `preset_sample`: the sample to which the process should be
            appended when creating a new process; see
            `utils.extract_preset_sample`

        :type user: `django.contrib.auth.models.User`
        :type process_instance: `samples.models_physical_processes.Process`
        :type preset_sample: `models.Sample`
        """
        super(SampleForm, self).__init__(*args, **kwargs)
        samples = list(user.my_samples.all())
        if process_instance:
            sample = process_instance.samples.get()
            samples.append(sample)
            self.fields["sample"].initial = sample.pk
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample"].initial = preset_sample.pk
        self.fields["sample"].set_samples(samples, user)
