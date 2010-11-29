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
import re, datetime, calendar, copy
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.db import models
from django.db.models import Q
from . import utils


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


class TextNullSearchField(SearchField):
    u"""Class for search fields containing text.  The match is
    case-insensitive, and partial matches are allowed, too.  Additionally, you
    may search for explicitly empty fields.
    """

    class TextNullForm(forms.Form):
        def clean(self):
            text = [value for key, value in self.cleaned_data.iteritems() if key.endswith("_main")][0]
            explicitly_empty = [value for key, value in self.cleaned_data.iteritems() if key.endswith("_null")][0]
            if explicitly_empty and text:
                raise forms.ValidationError(_(u"You can't search for empty values while giving a non-empty value."))
            return self.cleaned_data

    def parse_data(self, data, prefix):
        self.form = self.TextNullForm(data, prefix=prefix)
        self.form.fields[self.field.name + "_main"] = forms.CharField(label=unicode(self.field.verbose_name), required=False,
                                                                      help_text=self.field.help_text)
        self.form.fields[self.field.name + "_null"] = forms.BooleanField(label=_(u"explicitly empty"), required=False)

    def get_values(self):
        result = self.form.cleaned_data[self.field.name + "_main"]
        if result:
            return {self.query_path + "__icontains": result}
        elif self.form.cleaned_data[self.field.name + "_null"]:
            return {self.field.name + "__isnull": True}
        else:
            return {}


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
        self.form.fields[self.field.name + "_min"] = forms.DecimalField(
            label=unicode(self.field.verbose_name), required=False, help_text=self.field.help_text)
        self.form.fields[self.field.name + "_max"] = forms.DecimalField(
            label=unicode(self.field.verbose_name), required=False, help_text=self.field.help_text)


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


class DateTimeField(forms.Field):
    u"""Custom form field for timestamps that can be given blurrily.  For
    example, you can just give a year, or a year and a month.  You just can't
    start in the middle of a full timestamp.
    """

    datetime_pattern = re.compile(r"(?P<year>\d{4})(?:-(?P<month>\d{1,2})(?:-(?P<day>\d{1,2})"
                                  r"(?:\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{1,2})(?::(?P<second>\d{1,2})?)?)?)?)?)?$")

    def __init__(self, *args, **kwargs):
        self.start = kwargs.pop("start")
        super(DateTimeField, self).__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return None
        match = self.datetime_pattern.match(value)
        if not match:
            raise forms.ValidationError(_(u"The timestamp didn't match YYYY-MM-DD HH:MM:SS or a starting part of it."))
        year, month, day, hour, minute, second = match.groups()
        if self.start:
            year, month, day, hour, minute, second = \
                int(year), int(month or "1"), int(day or "1"), int(hour or "0"), int(minute or "0"), int(second or "0")
        else:
            year, month, day, hour, minute, second = \
                int(year), int(month or "12"), int(day or "0"), int(hour or "23"), int(minute or "59"), int(second or "59")
            if not day:
                day = [31, 0, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
            if not day:
                day = 29 if calendar.isleap(year) else 28
        return datetime.datetime(year, month, day, hour, minute, second)


class DateTimeSearchField(RangeSearchField):
    u"""Class for search fields containing timestamps.  It also exposes two
    fields for the user to give a range of dates.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name + "_min"] = DateTimeField(label=unicode(self.field.verbose_name), required=False,
                                                                   help_text=self.field.help_text, start=True)
        self.form.fields[self.field.name + "_max"] = DateTimeField(label=unicode(self.field.verbose_name), required=False,
                                                                   help_text=self.field.help_text, start=False)


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
        choices = [(model.__name__, model._meta.verbose_name) for model in models]
        choices.sort(key=lambda choice: unicode(choice[1]).lower())
        self.fields["_model"].choices = [("", u"---------")] + choices


all_searchable_models = None
def get_all_searchable_models():
    u"""Returns all model classes which have a ``get_search_tree_node`` method.

    :Return:
      all searchable model classes

    :rtype: list of ``class``
    """
    global all_searchable_models
    if all_searchable_models is None:
        all_searchable_models = []
        for model in utils.get_all_models().itervalues():
            if hasattr(model, "get_search_tree_node"):
                try:
                    model.get_search_tree_node()
                except NotImplementedError:
                    pass
                else:
                    all_searchable_models.append(model)
    return all_searchable_models


def get_search_results(search_tree, max_results, base_query=None):
    u"""Returns all found model instances for the given search.  It is a
    wrapper around the ``get_query_set`` method of the top-level node in the
    search tree, and it serves three purposes:

        1. It limits the number of found instances

        2. It converts the result query into a list of model instances.

        3. If the top-level node is abstract, it finds the actual instance for
           each found object.

    :Parameters:
      - `search_tree`: the complete search tree of the search
      - `max_results`: the maximal number of results to be returned
      - `base_query`: the query set to be used as the starting point of the
        query; it is used to restrict the found items to what the user is
        allowed to see

    :type search_tree: `SearchTreeNode`
    :type max_results: int
    :type base_query: ``QuerySet``

    :Return:
      the found objects, whether more than `max_results` were found

    :rtype: list of model instances, bool
    """
    results = search_tree.get_query_set(base_query)
    too_many_results = results.count() > max_results
    if too_many_results:
        results = results[:max_results]
    results = search_tree.model_class.objects.in_bulk(list(results.values_list("pk", flat=True))).values()
    if isinstance(search_tree, AbstractSearchTreeNode):
        results = [result.actual_instance for result in results]
    return results, too_many_results
    

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
            node = utils.get_all_models()[model_name].get_search_tree_node()
            parse_node = search_model_form.cleaned_data["_model"] == search_model_form.cleaned_data["_old_model"]
            node.parse_data(data if parse_node else None, new_prefix)
            search_model_form = SearchModelForm(self.related_models.keys(),
                                                initial={"_old_model": search_model_form.cleaned_data["_model"],
                                                         "_model": search_model_form.cleaned_data["_model"]},
                                                prefix=new_prefix)
            self.children.append((search_model_form, node))
            i += 1
        if self.related_models:
            self.children.append((SearchModelForm(self.related_models.keys(), prefix=new_prefix), None))

    def get_query_set(self, base_query=None):
        u"""Returns all model instances matching the search.

        :Parameters:
          - `base_query`: the query set to be used as the starting point of the
            query; it is only given at top level, and even then, it is
            optional; it is used to restrict the found items to what the user
            is allowed to see

        :type base_query: ``QuerySet``

        :Return:
          the search results

        :rtype: ``QuerySet``
        """
        result = base_query if base_query is not None else self.model_class.objects
        kwargs = {}
        for search_field in self.search_fields:
            if search_field.get_values():
                kwargs.update(search_field.get_values())
        result = result.filter(**kwargs)
        for __, node in self.children:
            if node:
                name = self.related_models[node.model_class] + "__pk__in"
                result = result.filter(**{name: node.get_query_set()})
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
            is_all_valid = search_field.is_valid() and is_all_valid
        if self.children:
            for __, node in self.children:
                if node:
                    is_all_valid = node.is_valid() and is_all_valid
        return is_all_valid


class AbstractSearchTreeNode(SearchTreeNode):

    class ChoiceSearchField(SearchField):
        u"""Class for search fields containing character/text fields with
        choices."""

        def __init__(self, field_label, derivatives, help_text):
            self.field_label = field_label
            self.help_text = help_text
            self.choices = [(derivative.__name__, derivative._meta.verbose_name) for derivative in derivatives]

        def parse_data(self, data, prefix):
            self.form = forms.Form(data, prefix=prefix)
            field = forms.ChoiceField(label=self.field_label, required=False, help_text=self.help_text)
            field.choices = [("", u"---------")] + self.choices
            self.form.fields["derivative"] = field

        def get_values(self):
            return {}


    def __init__(self, common_base_class, related_models, search_fields, derivatives,
                 choice_field_label=None, choice_field_help_text=None):
        super(AbstractSearchTreeNode, self).__init__(common_base_class, related_models, search_fields)
        self.derivatives = []
        for derivative in derivatives:
            node = SearchTreeNode(derivative, related_models, copy.copy(search_fields))
            node.children = self.children
            self.derivatives.append(node)
        self.derivative_choice = \
            self.ChoiceSearchField(choice_field_label or _(u"restrict to"), derivatives, choice_field_help_text)
        self.search_fields.append(self.derivative_choice)

    def get_query_set(self, base_query=None):
        result = base_query if base_query is not None else self.model_class.objects
        selected_derivative = self.derivative_choice.form.cleaned_data["derivative"]
        if not selected_derivative:
            selected_derivatives = self.derivatives
        else:
            try:
                selected_derivatives = [utils.get_all_models()[selected_derivative]]
            except KeyError:
                selected_derivatives = self.derivatives
        Q_expression = None
        for node in selected_derivatives:
            current_Q = Q(pk__in=node.get_query_set())
            if Q_expression:
                Q_expression |= current_Q
            else:
                Q_expression = current_Q
        if Q_expression:
            result = result.filter(Q_expression).distinct()
        return result.values("pk")
