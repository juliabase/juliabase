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
import django.utils.six as six
from django.utils.six.moves import cStringIO as StringIO

import copy, re, csv
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Max
from django.http import Http404, HttpResponse
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.contenttypes.models import ContentType
from django.template import defaultfilters
from jb_common import mimeparse
from jb_common.utils.base import camel_case_to_underscores
from samples import models, permissions
from samples.views.table_export import build_column_group_list, ColumnGroupsForm, \
    ColumnsForm, generate_table_rows, flatten_tree, OldDataForm, SwitchRowForm
import jb_common.utils.base
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from . import forms as utils
from .feed import Reporter
from .base import successful_response, extract_preset_sample, remove_samples_from_my_samples
from django.contrib.auth.decorators import login_required


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
                number_of_instances = subprocesses.count()
                instances = list(subprocesses.all()) + (len(indices) - number_of_instances) * [None]
                self.forms["subprocesses"] = [self.subform_class(self.data, prefix=str(index), instance=instance)
                                              for index, instance in zip(indices, instances)]
            else:
                self.forms["subprocesses"] = [self.subform_class(prefix=str(index), instance=subprocess)
                                              for index, subprocess in enumerate(subprocesses.all())]
        else:
            self.forms["subprocesses"] = []

    def save_to_database(self):
        process = super(SubprocessesMixin, self).save_to_database()
        getattr(self.process, self.subprocess_field).all().delete()
        for form in self.forms["subprocesses"]:
            subprocess = form.save(commit=False)
            setattr(subprocess, self.process_field, self.process)
            subprocess.save()
        return process
