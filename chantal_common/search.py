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


class OptionField(object):

    def __init__(self, cls, field_name):
        self.field = cls._meta.get_field(field_name)

    def parse_data(self, data, prefix):
        raise NotImplementedError

    def get_values(self):
        return {self.field.name: self.form.cleaned_data[self.field.name]}

    def is_valid(self):
        return self.form.is_valid()


class OptionTextField(OptionField):

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = forms.CharField(label=unicode(self.field.verbose_name), required=False)

    def get_values(self):
        return {self.field.name + "__icontains": self.form.cleaned_data[self.field.name]}


class OptionIntField(OptionField):
    
    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = forms.IntegerField(label=unicode(self.field.verbose_name), required=False)
    

class OptionTimeField(OptionField):

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = forms.DateTimeField(label=unicode(self.field.verbose_name), required=False)


class OptionGasField(OptionField):

    def __init__(self, field, data=None, **kwargs):
        super(OptionGasField, self).__init__(field, data, **kwargs)
        self.fields[field.name] = forms.CharField(label=field.name, required=False)
        self.fields["flow_rate"] = forms.DecimalField(label=_(u"flow rate"), required=False)

    def get_values(self):
        return {"channels__gas": self.changed_data[self.field.name],
                "channels__flow_rate": self.changed_data["flow_rate"]}


class SearchModelForm(forms.Form):
    _model = forms.ChoiceField(required=False)
    _old_model = forms.CharField(required=False)

    def __init__(self, models, data=None, **kwargs):
        super(SearchModelForm, self).__init__(data, **kwargs)
        self.fields["_model"].choices = [("", u"---------")] + \
            [(model.__name__, model._meta.verbose_name) for model in models]


all_models = None
def get_model(model_name):
    global all_models
    if all_models is None:
        all_models = {}
        # FixMe: Must be expanded to all apps, or the set of apps used here
        # must be taken from the settings.
        for app in [get_app("chantal_ipv"), get_app("samples"), get_app("chantal_common")]:
            all_models.update((model.__name__, model) for model in get_models(app))
    return all_models[model_name]


class ModelField(object):

    def __init__(self, model_class, related_models, attributes):
        self.related_models = related_models
        self.model_class = model_class
        self.children = []
        self.attributes = attributes

    def parse_data(self, data, prefix):
        for attribute in self.attributes:
            attribute.parse_data(data, prefix)
        if data is not None:
            depth = prefix.count("-") + (2 if prefix else 1)
            keys = [key for key in data if key.count("-") == depth]
            i = 1
            while True:
                new_prefix = prefix + ("-" if prefix else "") + str(i)
                if not data.get(new_prefix + "-_model"):
                    break
                search_model_form = SearchModelForm(self.related_models.keys(), data, prefix=new_prefix)
                if not search_model_form.is_valid():
                    break
                model_name = data[new_prefix + "-_model"]
                model_field = get_model(model_name).get_model_field()
                parse_model = search_model_form.cleaned_data["_model"] == search_model_form.cleaned_data["_old_model"]
                model_field.parse_data(data if parse_model else None, new_prefix)
                search_model_form = SearchModelForm(self.related_models.keys(),
                                                    initial={"_old_model": search_model_form.cleaned_data["_model"],
                                                             "_model": search_model_form.cleaned_data["_model"]},
                                                    prefix=new_prefix)
                self.children.append((search_model_form, model_field))
                i += 1
        if self.related_models:
            self.children.append((SearchModelForm(self.related_models.keys(), prefix=new_prefix), None))

    def get_search_results(self, top_level=True):
        kwargs = {}
        for attribute in self.attributes:
            if attribute.get_values():
                kwargs.update(attribute.get_values())
        result = self.model_class.objects.filter(**kwargs)
        kwargs = {}
        for child in self.children:
            if child[1]:
                name = self.related_models[child[1].model_class] + "__id__in"
                kwargs[name] = child[1].get_search_results(False)
        result = result.filter(**kwargs)
        if top_level:
            return self.model_class.objects.in_bulk(list(result.values_list("id", flat=True))).values()
        else:
            return result.values("id")

    def is_valid(self):
        is_all_valid = True
        for attribute in self.attributes:
            is_all_valid = is_all_valid and attribute.is_valid()
        if self.children:
            for child in self.children:
                if child[1]:
                    is_all_valid = is_all_valid and child[1].is_valid()
        return is_all_valid



