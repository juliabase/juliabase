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

from __future__ import absolute_import
from django import forms
from django.utils.translation import ugettext_lazy as _
from samples import models

class OptionField(forms.Form):
    def __init__(self, field, data=None, **kwargs):
        super(OptionField, self).__init__(data, **kwargs)
        self.field = field

    def get_values(self):
        if self.is_valid() and self.changed_data[self.field.name]:
            return {self.field.name: self.changed_data[self.field.name]}


class OptionTextField(OptionField):
    def __init__(self, field, data=None, **kwargs):
        super(OptionTextField, self).__init__(data, **kwargs)
        self.fields[field.name] = forms.CharField(label=field.verbose_name, required=False)

class OptionIntField(OptionField):
    def __init__(self, field, data=None, **kwargs):
        super(OptionIntField, self).__init__(data, **kwargs)
        self.fields[field.name] = forms.IntegerField(label=_(field.verbose_name).replace("_", " "), required=False)

class OptionTimeField(OptionField):
    def __init__(self, field, data=None, **kwargs):
        super(OptionTimeField, self).__init__(data, **kwargs)
        self.fields[field.name] = forms.DateTimeField(label=_(field.verbose_name).replace("_", " "), required=False)

class OptionGasField(OptionField):
    def __init__(self, field, data=None, **kwargs):
        super(OptionGasField, self).__init__(data, **kwargs)
        self.fields[field.name] = forms.CharField(label=_(field.verbose_name).replace("_", " "), required=False)
        self.fields["flow_rate"] = forms.DecimalField(label=_(u"flow rate"), required=False)

    def get_values(self):
        if self.is_valid() and self.changed_data[self.field.name] and self.changed_data["flow_rate"]:
            return {"channels__gas": self.changed_data[self.field.name],
                    "channels__flow_rate": self.changed_data["flow_rate"]}

class SearchSamplesForm(forms.Form):
    u"""Form for searching for samples.  So far, you can only enter a name
    substring for looking for samples.
    """
    name_pattern = forms.CharField(label=_(u"Name pattern"), max_length=30, required=False)
    aliases = forms.BooleanField(label=_(u"Include alias names"), required=False)


process_choices = list((key, _(models.physical_process_models[key]._meta.verbose_name)) for key in models.physical_process_models)
process_choices.insert(0, ('', u"---------"))

class ModelField(forms.Form):

    def __init__(self, model_class, related_models, data, **kwargs):
        self.model_class = model_class
        self.children = []
        self.attributes = []
        self.related_models = {}
        self.related_models.update(related_models)




    def get_search_results(self):
        kwargs = {}
        for attribute in self.attributes:
            kwargs.update(attribute.get_values())
        result = self.model_class.objects.filter(**kwargs)
        kwargs = {}
        for child in self.children:
            name = self.related_models[child.model_class] + "__id__in"
            kwargs[name] = child.get_search_results()
        result = result.filter(**kwargs)
        return result.values("id")

