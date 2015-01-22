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
from django.contrib.auth.decorators import login_required


__all__ = ("ProcessView",)


class ProcessView(TemplateView):
    multiple_samples = False

    def __init__(self, **kwargs):
        self.class_name = camel_case_to_underscores(self.model.__name__)
        self.template_name = "samples/edit_{}.html".format(self.class_name)
        super(ProcessView, self).__init__(**kwargs)
        self.forms = {}

    def startup(self):
        try:
            field_name = parameter_name = self.JBMeta.identifying_field
        except AttributeError:
            field_name, parameter_name = "id", self.class_name + "_id"
        self.id = self.kwargs[parameter_name]
        self.process = self.model.objects.get(**{field_name: self.id}) if self.id else None
        self.old_sample = self.process.samples.get() if self.process else None
        permissions.assert_can_add_edit_physical_process(self.request.user, self.process, self.model)
        self.preset_sample = utils.extract_preset_sample(self.request) if not self.process else None

    def build_forms(self):
        self.forms.update({"process": self.form(self.request.user, instance=self.process),
                           "sample": utils.SampleSelectForm(self.request.user, self.process, self.preset_sample),
                           "edit_description": utils.EditDescriptionForm() if self.process else None})

    def respond(self, request):
        title = _("Thickness of {sample}").format(sample=old_sample) if self.process else _("Add thickness")
        return render(request, "samples/edit_layer_thickness_measurement.html",
                      {"title": title, "measurement": layer_thickness_form, "sample": sample_form,
                       "edit_description": edit_description_form})

    def get(self, request, *args, **kwargs):
        self.startup()
        self.build_forms()
        return super(ProcessView, self).get(request, *args, **kwargs)

    def get_title(self):
        return _("Edit {process}").format(process=self.process) if self.process else \
            _("Add {class_name}").format(class_name=self.model._meta.verbose_name)

    def get_context_data(self, **kwargs):
        context = {}
        context["title"] = self.get_title()
        context.update(kwargs)
        context.update(self.forms)
        return super(ProcessView, self).get_context_data(**context)

    @classmethod
    def as_view(cls, **initkwargs):
        view = super(ProcessView, cls).as_view(**initkwargs)
        return login_required(view)
