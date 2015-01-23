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
from django.db.models import Q
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
from .base import successful_response, extract_preset_sample
from django.contrib.auth.decorators import login_required


__all__ = ("ProcessView", "ProcessMultipleSamplesView")


class ProcessWithoutSamplesView(TemplateView):

    def __init__(self, **kwargs):
        self.class_name = camel_case_to_underscores(self.model.__name__)
        self.template_name = "samples/edit_{}.html".format(self.class_name)
        super(ProcessWithoutSamplesView, self).__init__(**kwargs)
        self.forms = {}

    def startup(self):
        try:
            field_name = parameter_name = self.JBMeta.identifying_field
        except AttributeError:
            field_name, parameter_name = "id", self.class_name + "_id"
        self.id = self.kwargs[parameter_name]
        self.process = self.model.objects.get(**{field_name: self.id}) if self.id else None
        permissions.assert_can_add_edit_physical_process(self.request.user, self.process, self.model)
        self.preset_sample = extract_preset_sample(self.request) if not self.process else None
        self.data = self.request.POST or None

    def build_forms(self):
        self.forms.update({"process": self.form(self.request.user, self.data, instance=self.process),
                           "edit_description": utils.EditDescriptionForm(self.data) if self.id else None})

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
        if self.is_all_valid() and self.is_referentially_valid():
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
        self.forms["samples"] = utils.MultipleSamplesSelectForm(self.request.user, self.process, self.preset_sample,
                                                                self.data)

    def save_to_database(self):
        process = super(ProcessMultipleSamplesView, self).save_to_database()
        process.samples = self.forms["samples"].cleaned_data["sample_list"]
        return process
