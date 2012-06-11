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


"""
"""

from __future__ import absolute_import, unicode_literals

import datetime, re
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django import forms
from django.forms import widgets
from django.forms.util import ValidationError
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.contrib.auth.decorators import login_required
import chantal_common.utils
from chantal_common.utils import append_error
from samples import models, permissions
from samples.views import utils, feed_utils
from chantal_institute.views import form_utils
from django.utils.translation import ugettext , ugettext_lazy, ungettext
import chantal_institute.models as institute_models

_ = ugettext

class ProcessForm(form_utils.ProcessForm):
    """Model form for the main data.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, data=None, **kwargs):
        super(ProcessForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"style": "font-size: large", "size": "8"})
        process = kwargs.get("instance")
        self.fields["operator"].set_operator(process.operator if process else user, user.is_staff)
        self.fields["operator"].initial = process.operator.pk if process else user.pk
        self.fields["pressure"].widget.attrs["size"] = "10"
        self.fields["thickness"].widget.attrs["size"] = "10"
        self.fields["material"].widget.attrs["size"] = "10"
        self.user = user
        self.edit = False
        if process:
            self.edit = True

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `FormSet.__is_referentially_valid`.  I cannot use
        Django's built-in test anyway because it leads to an error message in
        wrong German (difficult to fix, even for the Django guys).
        """
        pass

    def clean_number(self):
        number = self.cleaned_data["number"]
        if number:
            if not re.match(datetime.date.today().strftime("%y") + r"E-\d{3,4}$", number):
                raise ValidationError(_("The evaporation number you have chosen isn't valid."))
            if institute_models.LargeEvaporation.objects.filter(number=number).exists() and not self.edit:
                raise ValidationError(_("The evaporation number you have chosen already exists."))
        return number

    class Meta:
        model = institute_models.LargeEvaporation
        exclude = ("external_operator",)


class FormSet(object):
    """Class for holding all forms of the large sputter deposition views, and for
    all methods working on these forms.

    :ivar process: the process to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``process``
      is the only way to distinguish between editing or creating.

    :type process: `institute_models.LargeEvaporation` or ``NoneType``
    """
    process_number_pattern = re.compile(r"(?P<prefix>\d\dA-)(?P<number>\d+)$")

    def __init__(self, request, process_number):
        """Class constructor.  The forms aren't created here – this
        is done later in `from_post_data` and in `from_database`.

        :Parameters:
          - `request`: the current HTTP Request object
          - `process_number`: number of the process to be edited.  If
            this is ``None``, create a new one.

        :type request: ``HttpRequest``
        :type depprocess_number: unicode
        """
        self.user = request.user
        self.user_details = self.user.samples_user_details
        self.process = \
            get_object_or_404(institute_models.LargeEvaporation, number=process_number) if process_number else None
        self.process_form = self.add_layers_form = self.samples_form = self.remove_from_my_samples_form = None
        self.preset_sample = utils.extract_preset_sample(request) if not self.process else None
        self.post_data = None

    def from_post_data(self, post_data):
        """Generate all forms from the post data submitted by the user.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data = post_data
        self.process_form = ProcessForm(self.user, self.post_data, instance=self.process)
        if not self.process:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(self.post_data)
        self.samples_form = form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.process, self.post_data)
        self.edit_description_form = form_utils.EditDescriptionForm(self.post_data) if self.deposition else None


    def from_database(self, query_dict):
        """Create all forms from database data.  This is used if the view was
        retrieved from the user with the HTTP GET method, so there hasn't been
        any post data submitted.

        I have to distinguish all three cases in this method: editing, copying,
        and duplication.

        :Parameters:
          - `query_dict`: dictionary with all given URL query string parameters

        :type query_dict: dict mapping unicode to unicode
        """

        copy_from = query_dict.get("copy_from")
        try:
            number = institute_models.LargeEvaporation.objects.latest('number').number
            number = "{0}{1:03}".format(number[:4], int(number[4:]) + 1)
        except:
            number = datetime.date.today().strftime("%y") + "E-001"
        if not self.process and copy_from:
            # Duplication of a process
            source_process_query = institute_models.LargeEvaporation.objects.filter(number=copy_from)
            if source_process_query.count() == 1:
                process_data = source_process_query.values()[0]
                process_data["timestamp"] = datetime.datetime.now()
                process_data["operator"] = self.user.pk
                process_data["number"] = number
                self.process_form = ProcessForm(self.user, initial=process_data)
        if not self.process_form:
            if self.process:
                # Normal edit of existing process
                self.process_form = ProcessForm(self.user, instance=self.process)
            else:
                # New deposition, or process has failed
                self.process_form = ProcessForm(
                    self.user, initial={"operator": self.user.pk, "timestamp": datetime.datetime.now(),
                                        "number": number})
        self.samples_form = form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.process)
        if not self.process:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm()
        self.edit_description_form = form_utils.EditDescriptionForm() if self.process else None

    def __is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.
        This function calls the ``is_valid()`` method of all forms, even if one
        of them returns ``False`` (and makes the return value clear
        prematurely).

        :Return:
          whether all forms are valid.

        :rtype: bool
        """
        all_valid = self.process_form.is_valid()
        all_valid = (self.edit_description_form.is_valid() if self.edit_description_form else True) and all_valid
        if not self.process:
            all_valid = self.remove_from_my_samples_form.is_valid() and all_valid
        if not self.process:
            all_valid = self.samples_form.is_valid() and all_valid
        return all_valid

    def __is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.  For example, no layer number must occur twice, and the
        process number must not exist within the database.

        Note that I test many situations here that cannot be achieved with
        using the browser because all number fields are read-only and thus
        inherently referentially valid.  However, the remote client (or a
        manipulated HTTP client) may be used in a malicious way, thus I have to
        test for *all* cases.

        :Return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.process_form.is_valid():
            if self.samples_form.is_valid():
                dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                       self.process_form.cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(
                        "The sample {samples} is already dead at this time.",
                        "The samples {samples} are already dead at this time.", len(dead_samples)).format(
                        samples=utils.format_enumeration([sample.name for sample in dead_samples]))
                    append_error(self.process_form, error_message, "timestamp")
                    referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        """Apply all layer changes, check the whole validity of the data, and
        save the forms to the database.  Only the process is just updated if
        it already existed.  However, the layers are completely deleted and
        re-constructed from scratch.

        :Return:
          The saved process object, or ``None`` if validation failed

        :rtype: `institute_models.LargeEvaporation` or ``NoneType``
        """
        database_ready = self.__is_all_valid()
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            process = self.process_form.save()
            if not self.process:
                # Change sample list only for *new* processes
                process.samples = self.samples_form.cleaned_data["sample_list"]
            feed_utils.Reporter(self.user).report_physical_process(
                process, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return process

    def get_context_dict(self):
        """Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :Return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"process": self.process_form,
                "samples": self.samples_form,
                "remove_from_my_samples": self.remove_from_my_samples_form,
                "edit_description": self.edit_description_form}


@login_required
def edit(request, process_number):
    """Edit or create a large evaporation plant process.  In case of creation,
    starting with a duplicate of another deposition is also possible if a
    ``copy-from`` query string parameter is present.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_number`: number of the process to be edited.  If this is
        ``None``, create a new one.

    :type request: ``HttpRequest``
    :type process_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    form_set = FormSet(request, process_number)
    ipv_model = institute_models.LargeEvaporation
    permissions.assert_can_add_edit_physical_process(request.user, form_set.process, ipv_model)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        process = form_set.save_to_database()
        if process:
            if form_set.remove_from_my_samples_form and \
                    form_set.remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(process.samples.all(), form_set.user)
            if process_number:
                return utils.successful_response(
                    request, _("Process {number} was successfully changed in the database.").format(number=process.number),
                    forced=True)
            else:
                samples = form_set.samples_form.cleaned_data["sample_list"]
                for sample in samples:
                    models.SampleAlias(name=process.number, sample=sample).save()
                    sample.save()
                return utils.successful_response(
                    request, _("Process {number} was successfully added to the database.").format(number=process.number),
                    forced=True, json_response=process.number)
    else:
        form_set.from_database(utils.parse_query_string(request))
    ipv_model_name = ipv_model._meta.verbose_name
    ipv_model_name = ipv_model_name[0].upper() + ipv_model_name[1:]
    title = _("Edit {name} “{number}”").format(name=ipv_model_name, number=process_number) if process_number \
        else _("Add {name}").format(name=ipv_model._meta.verbose_name)
    title = utils.capitalize_first_letter(title)
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render_to_response("samples/edit_large_evaporation.html", context_dict,
                              context_instance=RequestContext(request))
