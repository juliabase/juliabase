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


u"""Functions and classes for the advanced search.
"""

from __future__ import absolute_import
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.db.models import get_models, get_app
from django.db import models


def convert_fields_to_search_fields(cls, excluded_fieldnames=[]):
    u"""Generates search fields for (almost) all fields of the given model
    class.  This is to be used in a ``get_search_tree_node`` method.  It can
    only convert character/text fields, numerical fields, boolean fields, and
    fields with choices.

    Consider this routine a quick-and-dirty helper.  Sometimes it may be
    enough, sometimes you may have to refine its result afterwards.

    :Parameters:
      - `cls`: model class the fields of which should be converted to search
        field objects
      - `excluded_fieldnames`: fields with these names are not included into
        the list of search fields; ``"id"`` and ``"actual_object_id"`` are
        implicitly excluded

    :type cls: class (decendant of ``Model``)
    :type excluded_fieldnames: list of str

    :Return:
      the resulting search fields

    :rtype: list of `SearchField`
    """
    search_fields = []
    for field in cls._meta.fields:
        if field.name not in excluded_fieldnames + ["id", "actual_object_id"]:
            if field.choices:
                search_fields.append(ChoiceSearchField(cls, field))
            elif type(field) in [models.CharField, models.TextField]:
                search_fields.append(TextSearchField(cls, field))
            elif type(field) in [models.AutoField, models.BigIntegerField, models.IntegerField, models.FloatField,
                                 models.DecimalField, models.PositiveIntegerField, models.PositiveSmallIntegerField,
                                 models.SmallIntegerField]:
                search_fields.append(IntervalSearchField(cls, field))
            elif type(field) == models.DateTimeField:
                search_fields.append(DateTimeSearchField(cls, field))
            elif type(field) == models.BooleanField:
                search_fields.append(BooleanSearchField(cls, field))
    return search_fields


class SearchField(object):
    u"""Class representing one field in the advanced search.  This is an
    abstract base class for such fields.  It is instantiated in the
    ``get_search_tree_node`` methods in the models.

    Instances of this class contain a form usually containing only one field.
    This is shown on the web page of the advanced search as one searchable
    field.  It should not be required.

    :ivar form: The form containing the search field.  In some cases, it may
      contain more than one field, see `RangeSearchField` as an example.  This
      attribute is set only after `parse_data` was called.

    :ivar field: the original model field this search field bases upon

    :ivar query_path: the keyword parameter for Django's ``filter`` method of
      QuerySets for retrieving the field that this instance represents

    :type form: ``forms.Form``
    :type field: ``models.Field``
    :type query_path: str
    """

    def __init__(self, cls, field_or_field_name, additional_query_path=""):
        u"""Class constructor.

        :Parameters:
          - `cls`: model class to which the original model field belongs to;
            actually, it is only needed if `field_or_field_name` is a field
            name
          - `field_or_field_name`: the field to be represented as this seach
            field; you can call it by name, or pass the field itself
          - `additional_query_path`: if the model field is a related model,
            this parameter denotes the field within that model to be queried;
            for example, the currently responsible person for a sample needs
            ``"username"`` here

        :type cls: class (decendant of ``Model``)
        :type field_or_field_name: ``models.Field`` or str
        :type additional_query_path: str
        """
        self.field = cls._meta.get_field(field_or_field_name) if isinstance(field_or_field_name, basestring) \
            else field_or_field_name
        self.query_path = self.field.name
        if additional_query_path:
            self.query_path += "__" + additional_query_path

    def parse_data(self, data, prefix):
        u"""Create the web form representing this search field.  If ``data`` is
        not ``None``, it will be a bound form.

        :Parameters:
          - `data`: the GET parameters of the HTTP request; may be ``None`` if
            the form of this instance should be unbound
          - `prefix`: the prefix for the form

        :type data: ``QueryDict``
        :type prefix: str
        """
        raise NotImplementedError

    def get_values(self):
        u"""Returns keyword arguments for a ``filter`` call on a ``QuerySet``.
        Note that this implies that all keyword arguments returned here are
        “anded”.

        :Return:
          the keyword argument(s) for the ``filter`` call

        :rtype: dict mapping str to object
        """
        result = self.form.cleaned_data[self.field.name]
        return {self.query_path: result} if result is not None else {}

    def is_valid(self):
        u"""Retuns whethe the form within this search field is bound and valid.

        :Return:
          whether the form is valid

        :rtype: bool
        """
        return self.form.is_valid()


class RangeSearchField(SearchField):
    u"""Class for search fields with a from–to structure.  This is used for
    timestamps and numerical fields.  It is an abstract class.  At the same
    time, it is an example of a search field with more than one form field.
    """
    
    def get_values(self):
        result = {}
        min_value = self.form.cleaned_data[self.field.name + "_min"]
        max_value = self.form.cleaned_data[self.field.name + "_max"]
        if min_value is not None and max_value is not None:
            result[self.query_path + "__range"] = (min_value, max_value)
        elif min_value is not None:
            result[self.query_path + "__gte"] = min_value
        elif max_value is not None:
            result[self.query_path + "__lte"] = max_value
        return result


class TextSearchField(SearchField):
    u"""Class for search fields containing text.  The match is case-insensitive,
    and partial matches are allowed, too.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = forms.CharField(label=unicode(self.field.verbose_name), required=False,
                                                            help_text=self.field.help_text)

    def get_values(self):
        result = self.form.cleaned_data[self.field.name]
        return {self.query_path + "__icontains": result} if result else {}


class IntegerSearchField(SearchField):
    u"""Class for search fields containing integer values for which from–to
    ranges don't make sense.
    """
    
    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = forms.IntegerField(label=unicode(self.field.verbose_name), required=False,
                                                               help_text=self.field.help_text)


class IntervalSearchField(RangeSearchField):
    u"""Class for search fields containing numerical values (integer, decimal,
    float).  Its peculiarity is that it exposes a minimal and a maximal value.
    The user can fill out one of them, or both, or none.
    """
    
    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name + "_min"] = forms.FloatField(label=unicode(self.field.verbose_name), required=False,
                                                                      help_text=self.field.help_text)
        self.form.fields[self.field.name + "_max"] = forms.FloatField(label=unicode(self.field.verbose_name), required=False,
                                                                      help_text=self.field.help_text)


class ChoiceSearchField(SearchField):
    u"""Class for search fields containing character/text fields with choices.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        field = forms.ChoiceField(label=unicode(self.field.verbose_name), required=False, help_text=self.field.help_text)
        field.choices = [("", u"---------")] + list(self.field.choices)
        self.form.fields[self.field.name] = field

    def get_values(self):
        result = self.form.cleaned_data[self.field.name]
        return {self.query_path: result} if result else {}


class DateTimeSearchField(RangeSearchField):
    u"""Class for search fields containing timestamps.  It also exposes two
    fields for the user to give a range of dates.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name + "_min"] = forms.DateTimeField(label=unicode(self.field.verbose_name),
                                                                         required=False, help_text=self.field.help_text)
        self.form.fields[self.field.name + "_max"] = forms.DateTimeField(label=unicode(self.field.verbose_name),
                                                                         required=False, help_text=self.field.help_text)


class BooleanSearchField(SearchField):
    u"""Class for search fields containing boolean values.  The peculiarity of
    this field is that it gives the user three choices: yes, no, and “doesn't
    matter”.
    """

    class SimpleRadioSelectRenderer(forms.widgets.RadioFieldRenderer):
        def render(self):
            return mark_safe(u"""<ul class="radio-select">\n{0}\n</ul>""".format(u"\n".join(
                        u"<li>{0}</li>".format(force_unicode(w)) for w in self)))

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = forms.ChoiceField(
            label=unicode(self.field.verbose_name), required=False,
            choices=(("", _(u"doesn't matter")), ("yes", _(u"yes")), ("no", _(u"no"))),
            widget=forms.RadioSelect(renderer=self.SimpleRadioSelectRenderer), help_text=self.field.help_text)

    def get_values(self):
        result = self.form.cleaned_data[self.field.name]
        return {self.query_path: result == "yes"} if result else {}


class SearchModelForm(forms.Form):
    u"""Form for selecting the model which is contained in the current model.
    For example, you may select a process class which is connected with a
    sample.  Every node is associated with such a form, although it is kept
    with the node in a tuple by the parent node instead of in an attribute of
    the node itself.

    We also store the previously selected model here in order to know whether
    the following form fields (in the GET parameters) can be parsed into a
    bound form or whether we have to create an unbound new one.
    """
    _model = forms.ChoiceField(label=_(u"containing"), required=False)
    _old_model = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, models, data=None, **kwargs):
        super(SearchModelForm, self).__init__(data, **kwargs)
        self.fields["_model"].choices = [("", u"---------")] + \
            [(model.__name__, model._meta.verbose_name) for model in models]


all_models = None
def get_model(model_name):
    u"""Returns the model class of the given class name.

    :Parameters:
      - `model_name`: name of the model to be looked for

    :type model_name: str

    :Return:
      the model class

    :rtype: class (decendant of ``Model``)
    """
    global all_models
    if all_models is None:
        all_models = {}
        for app in [get_app(app.rpartition(".")[2]) for app in settings.INSTALLED_APPS]:
            all_models.update((model.__name__, model) for model in get_models(app))
    return all_models[model_name]


class SearchTreeNode(object):
    u"""Class which represents one node in the seach tree.  It is associated
    with a model class.

    :ivar related_models: All model classes which are offered as candidates for
      the “containing” selection field.  These are models to which the current
      model has a relation to, whether reverse or not doesn't matter.

      The dictionary maps model classes to their field names.  The field name
      is the name by which the related model can be accessed in ``filter``
      calls.

    :ivar model_class: the model class this tree node represents

    :ivar children: The child nodes of this node.  These are the related models
      which the user actually has selected.  They are stored together with the
      form (a `SearchModelForm`) on which they were selected.  The last entry
      in this list doesn't contain a tree node but only a form: it is the form
      with which the user can select a new child.

    :ivar search_fields: the search fields for this node, generated for the
      fields of the associated model class

    :type related_models: dict mapping class (decendant of ``Model``) to str
    :type model_class: class (decendant of ``Model``)
    :type children: list of (`SearchModelForm`, `SearchTreeNode`)
    :type search_fields: list of `SearchField`
    """

    def __init__(self, model_class, related_models, search_fields):
        u"""Class constructor.

        :Parameters:
          - `model_class`: the model class associated with this node
          - `related_models`: see the description of the instance variable of
            the same name
          - `search_fields`: see the description of the instance variable of
            the same name; they don't contain a form because their `parse_data`
            method has not been called yes

        :type model_class: class (decendant of ``Model``)
        :type related_models: dict mapping class (decendant of ``Model``) to
          str
        :type search_fields: list of `SearchField`
        """
        self.related_models = related_models
        self.model_class = model_class
        self.children = []
        self.search_fields = search_fields

    def parse_data(self, data, prefix):
        u"""Create all forms associated with this node (all the seach fields,
        and the `SearchModelForm` for all children), and create recursively the
        tree by creating the children.

        :Parameters:
          - `data`: the GET dictionary of the request; may be ``None`` if the
            forms of this node are supposed to be unbound (because it was newly
            created and there's nothing to be parsed into them)
          - `prefix`: The prefix for the forms.  Note that the form to select a
            model does not belong to the model to be selected but to its parent
            model.  This is also true for the prefixes: The top-level selection
            form (called ``root_form`` in
            ``samples.view.sample.advanced_search``) doesn't have a prefix,
            neither have the top-level search fields.  The children of a node
            have the next nesting depth of the prefix, including the
            `SearchModelForm` in which they were selected.  The starting number
            of prefixes is 1, and the nesting levels are separated by dashs.

        :type data: ``QueryDict`` or ``NoneType``
        :type prefix: str
        """
        for search_field in self.search_fields:
            search_field.parse_data(data, prefix)
        data = data or {}
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
            model_field = get_model(model_name).get_search_tree_node()
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

    def get_search_results(self, top_level=True, base_query=None):
        u"""Returns all model instances matching the search.

        :Parameters:
          - `top_level`: whether this is the top-level node of the tree
          - `base_query`: the query set to be used as the starting point of the
            query; it is only given if ``top_level==True``, and even then, it
            is optional; it is used to restrict the found items to what the
            user is allowed to see

        :type top_level: bool
        :type base_query: ``QuerySet``

        :Return:
          the search results

        :rtype: list of ``Model``
        """
        kwargs = {}
        for search_field in self.search_fields:
            if search_field.get_values():
                kwargs.update(search_field.get_values())
        result = base_query if base_query is not None else self.model_class.objects.filter(**kwargs)
        kwargs = {}
        for child in self.children:
            if child[1]:
                name = self.related_models[child[1].model_class] + "__pk__in"
                kwargs[name] = child[1].get_search_results(False)
        result = result.filter(**kwargs)
        if top_level:
            return self.model_class.objects.in_bulk(list(result.values_list("pk", flat=True))).values()
        else:
            return result.values("pk")

    def is_valid(self):
        u"""Returns whether the whole tree contains only bound and valid
        forms.  Note that the last children of each node – or, more precisely,
        the one without a `SearchTreeNode` in the tuple – is excluded from the
        test because it is always unbound.

        :Return:
          whether the whole tree contains only valid forms

        :rtype: bool
        """
        is_all_valid = True
        for search_field in self.search_fields:
            is_all_valid = is_all_valid and search_field.is_valid()
        if self.children:
            for child in self.children:
                if child[1]:
                    is_all_valid = is_all_valid and child[1].is_valid()
        return is_all_valid
