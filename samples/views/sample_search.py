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
from django.db.models import get_models, get_app


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

class SearchModelForm(forms.Form):
    _model = forms.ChoiceField()
    _old_model = forms.ChoiceField()

    def __init__(self, models, data=None, **kwargs):
        super(SearchModelForm, self).__init__(data, **kwargs)
        self.fields["_model"].choices = [("", u"---------")] + [(model.__name__, model._meta.verbose_name) for model in models]


class SearchSamplesForm(forms.Form):
    u"""Form for searching for samples.  So far, you can only enter a name
    substring for looking for samples.
    """
    name_pattern = forms.CharField(label=_(u"Name pattern"), max_length=30, required=False)
    aliases = forms.BooleanField(label=_(u"Include alias names"), required=False)


class ModelField:
    def __init__(self, model_class, related_models, attributes, data, **kwargs):
        self.related_models
        self.model_class = model_class
        self.children = []
        self.attributes = attributes
        prefix = kwargs.get("prefix", "")
        depth = prefix.count("-") +1
        keys = [key for key in data if key.count("-") == depth]
        all_models = {}
        for app in [get_app('chantal_ipv'), get_app('samples')]:
            all_models.update((model.__name__, model) for model in get_models(app))
        i = 1
        while True:
            new_prefix = prefix + str(i)  + "-"
            if new_prefix + "_model" not in keys:
                break
            model_name = data[new_prefix + "_model"]
            search_model_form = SearchModelForm(related_models.values(), data, prefix=new_prefix)
            parse_model = search_model_form.is_valid() and \
              search_model_form.changed_data["_model"] == search_model_form.changed_data["_old_model"]
            self.children.append((search_model_form,
                                  all_models[model_name].get_model_field(data if parse_model else None, new_prefix)))
            i += 1
        self.children.append((SearchModelForm(related_models.values(), prefix=new_prefix), None))


    def get_search_results(self):
        kwargs = {}
        for attribute in self.attributes:
            if attribute.get_values():
                kwargs.update(attribute.get_values())
        result = self.model_class.objects.filter(**kwargs)
        kwargs = {}
        for child in self.children:
            name = self.related_models[child[1].model_class] + "__id__in"
            kwargs[name] = child[1].get_search_results()
        result = result.filter(**kwargs)
        return result.values("id")





