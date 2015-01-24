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


from __future__ import absolute_import, unicode_literals

from django.db.models import Max
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy as _, ugettext
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
import django.forms as forms
from jb_common.utils.base import camel_case_to_underscores
from samples import permissions
from . import forms as utils
from .feed import Reporter
from .base import successful_response, extract_preset_sample, remove_samples_from_my_samples


__all__ = ("ProcessView", "ProcessMultipleSamplesView", "RemoveFromMySamplesMixin", "SubprocessesMixin")


class ProcessWithoutSamplesView(TemplateView):
    # Never derive from that; pointless.

    def __init__(self, **kwargs):
        self.class_name = camel_case_to_underscores(self.model.__name__)
        self.template_name = "samples/edit_{}.html".format(self.class_name)
        super(ProcessWithoutSamplesView, self).__init__(**kwargs)
        self.forms = {}

    def startup(self):
        try:
            self.identifying_field = parameter_name = self.model.JBMeta.identifying_field
        except AttributeError:
            self.identifying_field, parameter_name = "id", self.class_name + "_id"
        self.id = self.kwargs[parameter_name]
        self.process = self.model.objects.get(**{self.identifying_field: self.id}) if self.id else None
        permissions.assert_can_add_edit_physical_process(self.request.user, self.process, self.model)
        self.preset_sample = extract_preset_sample(self.request) if not self.process else None
        self.data = self.request.POST or None

    def get_next_id(self):
        return (self.model.objects.aggregate(Max(self.identifying_field))[self.identifying_field + "__max"] or 0) + 1

    def build_forms(self):
        if "process" not in self.forms:
            initial = {}
            if not self.id:
                next_id = self.get_next_id()
                if next_id:
                    initial[self.identifying_field] = next_id
            self.forms["process"] = self.form_class(self.request.user, self.data, instance=self.process, initial=initial)
        self.forms["edit_description"] = utils.EditDescriptionForm(self.data) if self.id else None

    def _check_validity(self, forms):
        all_valid = True
        for form in forms:
            if isinstance(form, (list, tuple)):
                all_valid = self._check_validity(form) and all_valid
            elif form is not None:
                all_valid = form.is_valid() and all_valid
        return all_valid
        
    def is_all_valid(self):
        return self._check_validity(self.forms.values())

    def is_referentially_valid(self):
        return True

    def save_to_database(self):
        process = self.forms["process"].save()
        return process

    def get(self, request, *args, **kwargs):
        self.startup()
        self.build_forms()
        return super(ProcessWithoutSamplesView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.startup()
        self.build_forms()
        all_valid = self.is_all_valid()
        referentially_valid = self.is_referentially_valid()
        if all_valid and referentially_valid:
            self.process = self.save_to_database()
            Reporter(request.user).report_physical_process(
                self.process, self.forms["edit_description"].cleaned_data if self.forms["edit_description"] else None)
            success_report = _("{process} was successfully changed in the database."). \
                format(process=self.process) if self.id else \
                _("{measurement} was successfully added to the database.").format(measurement=self.process)
            return successful_response(request, success_report, json_response=self.process.pk)
        else:
            return super(ProcessWithoutSamplesView, self).get(request, *args, **kwargs)

    def get_title(self):
        return _("Edit {process}").format(process=self.process) if self.id else \
            _("Add {class_name}").format(class_name=self.model._meta.verbose_name)

    def get_context_data(self, **kwargs):
        context = {}
        context["title"] = self.get_title()
        context.update(kwargs)
        context.update(self.forms)
        return super(ProcessWithoutSamplesView, self).get_context_data(**context)

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(ProcessWithoutSamplesView, cls).as_view(**initkwargs)
        return login_required(view)


class ProcessView(ProcessWithoutSamplesView):

    def build_forms(self):
        super(ProcessView, self).build_forms()
        if "sample" not in self.forms:
            self.forms["sample"] = utils.SampleSelectForm(self.request.user, self.process, self.preset_sample, self.data)

    def is_referentially_valid(self):
        referentially_valid = super(ProcessView, self).is_referentially_valid()
        referentially_valid = referentially_valid and self.forms["process"].is_referentially_valid(self.forms["sample"])
        return referentially_valid

    def save_to_database(self):
        process = super(ProcessView, self).save_to_database()
        process.samples = [self.forms["sample"].cleaned_data["sample"]]
        return process


class ProcessMultipleSamplesView(ProcessWithoutSamplesView):

    def build_forms(self):
        super(ProcessMultipleSamplesView, self).build_forms()
        if "samples" not in self.forms:
            self.forms["samples"] = utils.MultipleSamplesSelectForm(self.request.user, self.process, self.preset_sample,
                                                                    self.data)

    def save_to_database(self):
        process = super(ProcessMultipleSamplesView, self).save_to_database()
        process.samples = self.forms["samples"].cleaned_data["sample_list"]
        return process


class RemoveFromMySamplesMixin(ProcessWithoutSamplesView):
    # Must be derived from first

    def build_forms(self):
        super(RemoveFromMySamplesMixin, self).build_forms()
        self.forms["remove_from_my_samples"] = utils.RemoveFromMySamplesForm(self.data) if not self.id else None

    def save_to_database(self):
        process = super(RemoveFromMySamplesMixin, self).save_to_database()
        if self.forms["remove_from_my_samples"] and \
           self.forms["remove_from_my_samples"].cleaned_data["remove_from_my_samples"]:
            remove_samples_from_my_samples(process.samples.all(), self.request.user)
        return process


class NumberForm(forms.Form):
    number = forms.IntegerField(label=_("number of subprocesses"), min_value=1)


class SubprocessesMixin(ProcessWithoutSamplesView):
    # Must be derived from first

    def build_forms(self):
        super(SubprocessesMixin, self).build_forms()
        if self.id:
            subprocesses = getattr(self.process, self.subprocess_field)
            if not self.sub_model._meta.ordering:
                subprocesses = subprocesses.order_by("id")
            if self.request.method == "POST":
                indices = utils.collect_subform_indices(self.data)
                self.forms["number"] = NumberForm(self.data)
                if self.forms["number"].is_valid():
                    new_number_of_forms = self.forms["number"].cleaned_data["number"]
                    indices = indices[:new_number_of_forms]
                else:
                    new_number_of_forms = len(indices)
                instances = list(subprocesses.all()) + (len(indices) - subprocesses.count()) * [None]
                self.forms["subprocesses"] = [self.subform_class(self.data, prefix=str(index), instance=instance)
                                              for index, instance in zip(indices, instances)]
                number_of_new_forms = new_number_of_forms - len(indices)
                if number_of_new_forms > 0:
                    self.forms["subprocesses"].extend([self.subform_class(prefix=str(index))
                                                       for index in range(max(indices) + 1, max(indices) + 1 + number_of_new_forms)])
            else:
                self.forms["number"] = NumberForm(initial={"number": subprocesses.count()})
                self.forms["subprocesses"] = [self.subform_class(prefix=str(index), instance=subprocess)
                                              for index, subprocess in enumerate(subprocesses.all())]
        else:
            self.forms["subprocesses"] = []

    def is_referentially_valid(self):
        referentially_valid = super(SubprocessesMixin, self).is_referentially_valid()
        if not self.forms["subprocesses"]:
            self.forms["process"].add_error(None, _("No subprocesses given."))
            referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        process = super(SubprocessesMixin, self).save_to_database()
        getattr(self.process, self.subprocess_field).all().delete()
        for form in self.forms["subprocesses"]:
            subprocess = form.save(commit=False)
            setattr(subprocess, self.process_field, self.process)
            subprocess.save()
        return process


_ = ugettext
