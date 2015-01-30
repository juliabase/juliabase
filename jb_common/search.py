#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Functions and classes for the advanced search.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six
from django.utils.encoding import python_2_unicode_compatible

import re, datetime, calendar, copy
from django import forms
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _, ugettext
from django.conf import settings
from django.db import models
from django.db.models import Q
import jb_common.utils.base as utils
from jb_common import model_fields


def convert_fields_to_search_fields(cls, excluded_fieldnames=[]):
    """Generates search fields for (almost) all fields of the given model
    class.  This is to be used in a ``get_search_tree_node`` method.  It can
    only convert character/text fields, numerical fields, boolean fields, and
    fields with choices.

    Consider this routine a quick-and-dirty helper.  Sometimes it may be
    enough, sometimes you may have to refine its result afterwards.

    :param cls: model class the fields of which should be converted to search
        field objects
    :param excluded_fieldnames: fields with these names are not included into
        the list of search fields; ``"id"`` and ``"actual_object_id"`` are
        implicitly excluded

    :type cls: class (decendant of models.Model)
    :type excluded_fieldnames: list of str

    :return:
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
            elif type(field) in [model_fields.DecimalQuantityField, model_fields.FloatQuantityField,
                                 model_fields.IntegerQuantityField, model_fields.PositiveIntegerQuantityField,
                                 model_fields.PositiveSmallIntegerQuantityField, model_fields.SmallIntegerQuantityField]:
                search_fields.append(IntervalQuantitySearchField(cls, field))
            elif type(field) == models.DateTimeField:
                search_fields.append(DateTimeSearchField(cls, field))
            elif type(field) == models.BooleanField:
                search_fields.append(BooleanSearchField(cls, field))
    return search_fields


@python_2_unicode_compatible
class SearchField(object):
    """Class representing one field in the advanced search.  This is an
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
      QuerySets for retrieving the field that this instance represents; if
      ``None``, the field name is used instead, but see the ``query_paths``
      parameter in `get_values`.

    :type form: forms.Form
    :type field: models.Field
    :type query_path: str
    """

    def __init__(self, cls, field_or_field_name, additional_query_path=""):
        """
        :param cls: model class to which the original model field belongs to;
            actually, it is only needed if `field_or_field_name` is a field
            name
        :param field_or_field_name: the field to be represented as this seach
            field; you can call it by name, or pass the field itself
        :param additional_query_path: if the model field is a related model,
            this parameter denotes the field within that model to be queried;
            for example, the currently responsible person for a sample needs
            ``"username"`` here

        :type cls: class (decendant of models.Model)
        :type field_or_field_name: models.Field or str
        :type additional_query_path: str
        """
        self.field = cls._meta.get_field(field_or_field_name) if isinstance(field_or_field_name, six.string_types) \
            else field_or_field_name
        if additional_query_path:
            self.query_path = self.field.name + "__" + additional_query_path
        else:
            self.query_path = None

    def parse_data(self, data, prefix):
        """Create the web form representing this search field.  If ``data`` is
        not ``None``, it will be a bound form.

        :param data: the GET parameters of the HTTP request; may be ``None`` if
            the form of this instance should be unbound
        :param prefix: the prefix for the form

        :type data: QueryDict
        :type prefix: str
        """
        raise NotImplementedError

    def get_query_path(self, query_paths):
        """Returns the query path for the ``filter`` method call of a
        QuerySet for the model field of this `SearchField`.  Normally, the
        query path is simply the field name, possibly extended by the
        ``additional_query_path`` parameter of ``__init__``.  However, if the
        `query_path` parameter contains the fieldname as a key, the
        corresponding value is used instead.

        :param query_paths: dictionary mapping field names to query paths ready
            to be used in a ``filter`` method call of a QuerySet.

        :type: dict mapping str to str

        :return:
          the query path snippet

        :rtype: str
        """
        return query_paths.get(self.field.name) or self.query_path or self.field.name

    def get_values(self, query_paths={}):
        """Returns keyword arguments for a ``filter`` call on a QuerySet.
        Note that this implies that all keyword arguments returned here are
        “anded”.

        :param query_paths: dictionary mapping field names to query paths ready
            to be used in a ``filter`` method call of a QuerySet.

            This parameter is not used in JuliaBase-samples but it may be
            interesting for institute-specific code if some models should be
            combined into one search tree node.  Then, a derivative of
            `SearchTreeNode` may use this parameter in order to trigger
            different searches from the same ``SearchField``.

        :type: dict mapping str to str

        :return:
          the keyword argument(s) for the ``filter`` call

        :rtype: dict mapping str to object
        """
        result = self.form.cleaned_data[self.field.name]
        return {self.get_query_path(query_paths): result} if result is not None else {}

    def is_valid(self):
        """Retuns whether the form within this search field is bound and
        valid.

        :return:
          whether the form is valid

        :rtype: bool
        """
        return self.form.is_valid()

    def __str__(self):
        """Returns a unicode representation of this search field.  It is only
        useful for debugging purposes.  Note that if a derived class doesn't
        store a model field in ``self.field``, this must be overridden.
        """
        return '"{0}"'.format(self.field.verbose_name)


class RangeSearchField(SearchField):
    """Class for search fields with a from–to structure.  This is used for
    timestamps and numerical fields.  It is an abstract class.  At the same
    time, it is an example of a search field with more than one form field.
    """

    def get_values(self, query_paths={}):
        result = {}
        min_value = self.form.cleaned_data[self.field.name + "_min"]
        max_value = self.form.cleaned_data[self.field.name + "_max"]
        query_path = self.get_query_path(query_paths)
        if min_value is not None and max_value is not None:
            result[query_path + "__range"] = (min_value, max_value)
        elif min_value is not None:
            result[query_path + "__gte"] = min_value
        elif max_value is not None:
            result[query_path + "__lte"] = max_value
        return result


class TextSearchField(SearchField):
    """Class for search fields containing text.  The match is case-insensitive,
    and partial matches are allowed, too.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = self.field.formfield(required=False)

    def get_values(self, query_paths={}):
        result = self.form.cleaned_data[self.field.name]
        return {self.get_query_path(query_paths) + "__icontains": result} if result else {}


class TextNullSearchField(SearchField):
    """Class for search fields containing text.  The match is case-insensitive, and
    partial matches are allowed, too.  Additionally, you may search for
    explicitly empty fields.
    """

    class TextNullForm(forms.Form):
        def clean(self):
            cleaned_data = super(TextNullSearchField.TextNullForm, self).clean()
            text = [value for key, value in self.cleaned_data.items() if key.endswith("_main")][0]
            explicitly_empty = [value for key, value in self.cleaned_data.items() if key.endswith("_null")][0]
            if explicitly_empty and text:
                raise forms.ValidationError(_("You can't search for empty values while giving a non-empty value."))
            return cleaned_data

    def parse_data(self, data, prefix):
        self.form = self.TextNullForm(data, prefix=prefix)
        self.form.fields[self.field.name + "_main"] = self.field.formfield(required=False)
        self.form.fields[self.field.name + "_null"] = forms.BooleanField(label=_("explicitly empty"), required=False)

    def get_values(self, query_paths={}):
        result = self.form.cleaned_data[self.field.name + "_main"]
        query_path = self.get_query_path(query_paths)
        if result:
            return {query_path + "__icontains": result}
        elif self.form.cleaned_data[self.field.name + "_null"]:
            return {query_path + "__isnull": True}
        else:
            return {}


class IntegerSearchField(SearchField):
    """Class for search fields containing integer values for which from–to
    ranges don't make sense.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = self.field.formfield(required=False)


class IntervalSearchField(RangeSearchField):
    """Class for search fields containing numerical values (integer, decimal,
    float).  Its peculiarity is that it exposes a minimal and a maximal value.
    The user can fill out one of them, or both, or none.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name + "_min"] = self.field.formfield(required=False)
        self.form.fields[self.field.name + "_max"] = self.field.formfield(required=False)

class IntervalQuantitySearchField(RangeSearchField):
    """Class for search fields containing numerical values (integer, decimal,
    float) with units.  Its peculiarity is that it exposes a minimal and a maximal value.
    The user can fill out one of them, or both, or none.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name + "_min"] = self.field.formfield(required=False)
        self.form.fields[self.field.name + "_max"] = self.field.formfield(required=False)


class ChoiceSearchField(SearchField):
    """Class for search fields containing character/text fields with choices.

    FixMe: This could be changed to a ``MultipleChoiceField`` sometime.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = self.field.formfield(required=False,
                                                                 choices=[("", "---------")] + list(self.field.choices))

    def get_values(self, query_paths={}):
        result = self.form.cleaned_data[self.field.name]
        return {self.get_query_path(query_paths): result} if result else {}


class DateTimeField(forms.Field):
    """Custom form field for timestamps that can be given blurrily.  For
    example, you can just give a year, or a year and a month.  You just can't
    start in the middle of a full timestamp.  You must pass the boolean
    ``start`` keyword argument to this field so that it know whether it should
    fill missing slots (days, hours etc) with the _smallest_ possible values or
    the _biggest_ ones.

    Additionally, you can tell the field with an optional
    ``with_inaccuracy=True`` to give a 2-tuple back, with the inaccuracy as the
    second item.
    """

    datetime_pattern = re.compile(r"(?P<year>\d{4})(?:-(?P<month>\d{1,2})(?:-(?P<day>\d{1,2})"
                                  r"(?:\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{1,2})(?::(?P<second>\d{1,2})?)?)?)?)?)?$")

    def __init__(self, *args, **kwargs):
        self.start = kwargs.pop("start")
        self.with_inaccuracy = kwargs.pop("with_inaccuracy", False)
        super(DateTimeField, self).__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return None
        match = self.datetime_pattern.match(value)
        if not match:
            raise forms.ValidationError(_("The timestamp didn't match YYYY-MM-DD HH:MM:SS or a starting part of it."))
        year, month, day, hour, minute, second = match.groups()
        if self.with_inaccuracy:
            if month is None:
                inaccuracy = 5
            elif day is None:
                inaccuracy = 4
            elif hour is None:
                inaccuracy = 3
            elif minute is None:
                inaccuracy = 2
            elif second is None:
                inaccuracy = 1
            else:
                inaccuracy = 0
        if self.start:
            year, month, day, hour, minute, second = \
                int(year), int(month or "1"), int(day or "1"), int(hour or "0"), int(minute or "0"), int(second or "0")
        else:
            year, month, day, hour, minute, second = \
                int(year), int(month or "12"), int(day or "0"), int(hour or "23"), int(minute or "59"), int(second or "59")
            if not day:
                day = [31, None, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
            if not day:
                day = 29 if calendar.isleap(year) else 28
        try:
            timestamp = datetime.datetime(year, month, day, hour, minute, second)
        except ValueError:
            raise forms.ValidationError(_("Invalid date or time."))
        return (timestamp, inaccuracy) if self.with_inaccuracy else timestamp


class DateTimeSearchField(RangeSearchField):
    """Class for search fields containing timestamps.  It also exposes two
    fields for the user to give a range of dates.
    """

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name + "_min"] = self.field.formfield(form_class=DateTimeField, required=False, start=True)
        self.form.fields[self.field.name + "_max"] = self.field.formfield(form_class=DateTimeField, required=False, start=False)


class BooleanSearchField(SearchField):
    """Class for search fields containing boolean values.  The peculiarity of
    this field is that it gives the user three choices: yes, no, and “doesn't
    matter”.
    """

    class SimpleRadioSelectRenderer(forms.widgets.RadioFieldRenderer):
        def render(self):
            return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                        "<li>{0}</li>".format(force_text(w)) for w in self)))

    def parse_data(self, data, prefix):
        self.form = forms.Form(data, prefix=prefix)
        self.form.fields[self.field.name] = self.field.formfield(form_class=forms.ChoiceField, required=False,
                                                choices=(("", _("doesn't matter")), ("yes", _("yes")), ("no", _("no"))),
                                                widget=forms.RadioSelect(renderer=self.SimpleRadioSelectRenderer))

    def get_values(self, query_paths={}):
        result = self.form.cleaned_data[self.field.name]
        return {self.get_query_path(query_paths): result == "yes"} if result else {}


class SearchModelForm(forms.Form):
    """Form for selecting the model which is contained in the current model.
    For example, you may select a process class which is connected with a
    sample.  Every node is associated with such a form, although it is kept
    with the node in a tuple by the parent node instead of in an attribute of
    the node itself.

    We also store the previously selected model here in order to know whether
    the following form fields (in the GET parameters) can be parsed into a
    bound form or whether we have to create an unbound new one.

    In the third field we can store a hash value from the input values to
    specify whether the user has changed something in the search view.
    """
    _model = forms.ChoiceField(label=_("containing"), required=False)
    _old_model = forms.CharField(widget=forms.HiddenInput, required=False)
    _search_parameters_hash = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, models, data=None, **kwargs):
        super(SearchModelForm, self).__init__(data, **kwargs)
        choices = [(model.__name__, model._meta.verbose_name) for model in models]
        choices.sort(key=lambda choice: six.text_type(choice[1]).lower())
        self.fields["_model"].choices = [("", "---------")] + choices


class SetLockedException(Exception):
    """Exception class raised when `all_searchable_models` is accessed
    although it is not completely built yet.  This is only an internal
    exception class.  This way, I can call the ``get_search_tree_node`` method
    in `get_all_searchable_models` in order to detect whether a model is
    searchable.  Note that ``get_search_tree_node`` in turn calls
    `get_all_searchable_models`.

    Otherwise, I would have to define another method just to detect whether a
    model is searchable.
    """
    pass

all_searchable_models = None
def get_all_searchable_models():
    """Returns all model classes which have a ``get_search_tree_node`` method.

    :return:
      all searchable model classes

    :rtype: frozenset of ``class``
    """
    global all_searchable_models
    if not isinstance(all_searchable_models, frozenset):
        if isinstance(all_searchable_models, set):
            raise SetLockedException
        all_searchable_models = set()
        for model in utils.get_all_models().values():
            if hasattr(model, "get_search_tree_node"):
                try:
                    model.get_search_tree_node()
                except NotImplementedError:
                    pass
                except SetLockedException:
                    all_searchable_models.add(model)
                else:
                    all_searchable_models.add(model)
    all_searchable_models = frozenset(all_searchable_models)
    return all_searchable_models


def get_search_results(search_tree, max_results, base_query=None):
    """Returns all found model instances for the given search.  It is a
    wrapper around the ``get_query_set`` method of the top-level node in the
    search tree, and it serves three purposes:

        1. It limits the number of found instances

        2. It converts the result query into a list of model instances.

        3. If the top-level node is abstract, it finds the actual instance for
           each found object.

    :param search_tree: the complete search tree of the search
    :param max_results: the maximal number of results to be returned
    :param base_query: the query set to be used as the starting point of the
        query; it is used to restrict the found items to what the user is
        allowed to see

    :type search_tree: `SearchTreeNode`
    :type max_results: int
    :type base_query: QuerySet

    :return:
      the found objects, whether more than ``max_results`` were found

    :rtype: list of model instances, bool
    """
    results = search_tree.get_query_set(base_query).distinct()
    too_many_results = results.count() > max_results
    if too_many_results:
        results = results[:max_results]
    # FixMe: This intermediate ``pks`` variable is necessary until
    # https://code.djangoproject.com/ticket/24254 isn't fixed.
    pks = list(results.values_list("pk", flat=True))
    results = search_tree.model_class.objects.filter(pk__in=pks)
    if isinstance(search_tree, AbstractSearchTreeNode):
        results = [result.actual_instance for result in results]
    return results, too_many_results


@python_2_unicode_compatible
class SearchTreeNode(object):
    """Class which represents one node in the seach tree.  It is associated
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

    :type related_models: dict mapping class (decendant of models.Model) to str
    :type model_class: class (decendant of models.Model)
    :type children: list of (`SearchModelForm`, `SearchTreeNode`)
    :type search_fields: list of `SearchField`
    """

    def __init__(self, model_class, related_models, search_fields):
        """Class constructor.

        :param model_class: the model class associated with this node
        :param related_models: see the description of the instance variable of
            the same name
        :param search_fields: see the description of the instance variable of
            the same name; they don't contain a form because their `parse_data`
            method has not been called yet

        :type model_class: class (decendant of models.Model)
        :type related_models: dict mapping class (decendant of models.Model) to
          str
        :type search_fields: list of `SearchField`
        """
        self.related_models = related_models
        self.model_class = model_class
        self.children = []
        self.search_fields = search_fields

    def parse_data(self, data, prefix):
        """Create all forms associated with this node (all the seach fields,
        and the `SearchModelForm` for all children), and create recursively the
        tree by creating the children.

        :param data: the GET dictionary of the request; may be ``None`` if the
            forms of this node are supposed to be unbound (because it was newly
            created and there's nothing to be parsed into them)
        :param prefix: The prefix for the forms.  Note that the form to select a
            model does not belong to the model to be selected but to its parent
            model.  This is also true for the prefixes: The top-level selection
            form (called ``root_form`` in
            ``samples.view.sample.advanced_search``) doesn't have a prefix,
            neither have the top-level search fields.  The children of a node
            have the next nesting depth of the prefix, including the
            `SearchModelForm` in which they were selected.  The starting number
            of prefixes is 1, and the nesting levels are separated by dashs.

        :type data: QueryDict or NoneType
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
        """Returns all model instances matching the search.

        :param base_query: the query set to be used as the starting point of the
            query; it is only given at top level, and even then, it is
            optional; it is used to restrict the found items to what the user
            is allowed to see

        :type base_query: QuerySet

        :return:
          the search results

        :rtype: QuerySet
        """
        result = base_query if base_query is not None else self.model_class.objects
        kwargs = {}
        for search_field in self.search_fields:
            values = search_field.get_values()
            if values:
                kwargs.update(values)
        result = result.filter(**kwargs)
        for __, node in self.children:
            if node:
                name = self.related_models[node.model_class] + "__pk__in"
                result = result.filter(**{name: node.get_query_set()})
        return result.only("pk")

    def is_valid(self):
        """Returns whether the whole tree contains only bound and valid
        forms.  Note that the last children of each node – or, more precisely,
        the one without a `SearchTreeNode` in the tuple – is excluded from the
        test because it is always unbound.

        :return:
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

    def __str__(self):
        """Returns a unicode representation of this node and its subtree.  It
        is only useful for debugging purposes.
        """
        choices_last_child = self.children[-1][0].fields["_model"].choices if self.children else []
        return "({0}[{1}]: {2};{3})".format(
            self.model_class.__name__,
            ",".join(choice[0] for choice in choices_last_child if choice[0]),
            ",".join(six.text_type(search_field) for search_field in self.search_fields),
            ",".join(six.text_type(child[1]) for child in self.children if child[1]))


class AbstractSearchTreeNode(SearchTreeNode):
    """Class representing a search tree node which is not connected with a
    particular model.  This way, similar models can be combined to one
    selection in the advanced search.  They must share a common set of fields
    though, and these fields must have the same names in the models.  If you
    need more flexibility, you can make your own derived class from
    `SearchTreeNode`.  See the ``query_paths`` parameter of
    :py:meth:`SearchField.get_values` for more information.

    An abstract node has a list of *derivatives*.  Derivatives are ordinary
    search tree nodes, typically representing non-abstrict model classes, to
    which the search fields are passed.  This means that an abstract node
    doesn't search in the search fields itself.  Instead, it lets the
    derivatives search and combines the results with the “or” operator.  Thus,
    it *any* of the derivatives returns a match, it is included into the search
    results (which may be filtered further, of course).

    For example, we have three Raman apparatuses in our institute IEK-5/FZJ.
    All three share exactly the same model fields.  Therefore, there is an
    abstract model class that all three concrete models are derived from.
    However, if you look for a certain Raman measurement, you don't know a
    priori in which if the three apparatuses it was measured.  Hence, there is
    only *one* Raman selection in the advanced view, which looks for results in
    all three models.  Note that it is still possible to focus a search to one
    particular Raman model.

    In case of Raman, the non-abstract models doesn't occur in the search form.
    However, it is also possible to have both the abstract node and all
    derivatives in the search form.  For this, you just have to give working
    ``get_search_tree_node`` methods in the derivative model classes as well.
    """

    class ChoiceSearchField(SearchField):
        """Class for a special search field for selecting a derivative.

        FixMe: This could be changed to a ``MultipleChoiceField`` sometime.
        """

        def __init__(self, field_label, derivatives, help_text):
            self.field_label = field_label
            self.help_text = help_text
            self.choices = [(derivative.__name__, derivative._meta.verbose_name) for derivative in derivatives]

        def parse_data(self, data, prefix):
            self.form = forms.Form(data, prefix=prefix)
            field = forms.ChoiceField(label=self.field_label, required=False, help_text=self.help_text)
            field.choices = [("", "---------")] + self.choices
            self.form.fields["derivative"] = field

        def get_values(self, query_paths={}):
            # Should never be called anyway because this search field is not
            # passed to the derivatives.
            return {}


    def __init__(self, common_base_class, related_models, search_fields, derivatives,
                 choice_field_label=None, choice_field_help_text=None):
        """Class constructor.

        :param common_base_class: the model which is a common base class for all
            derivatives; this is necessary so that the returned pk values in
            `get_query_set` refer to one particular database table
        :param related_models: see the description of the instance variable of
            the same name in `SearchTreeNode`
        :param search_fields: see the description of the instance variable of
            the same name in `SearchTreeNode`; they don't contain a form
            because their `parse_data` method has not been called yet
        :param derivatives: the models that are combined in this abstract node
        :param choice_field_label: Label for the choice form field for selecting
            a derivative.  By default, the label reads “restricted to”.
        :param choice_field_help_text: help text for the form field for
            selecting a derivative

        :type common_base_class: class (decendant of models.Model)
        :type related_models: dict mapping class (decendant of models.Model) to
          str
        :type search_fields: list of `SearchField`
        :type derivatives: list of class (decendant of models.Model)
        :type choice_field_label: unicode
        :type choice_field_help_text: unicode
        """
        super(AbstractSearchTreeNode, self).__init__(common_base_class, related_models, search_fields)
        self.derivatives = []
        for derivative in derivatives:
            node = SearchTreeNode(derivative, related_models, copy.copy(search_fields))
            node.children = self.children
            self.derivatives.append(node)
        self.derivative_choice = \
            self.ChoiceSearchField(choice_field_label or _("restrict to"), derivatives, choice_field_help_text)
        # Note that this is not appended to the ``search_fields`` of the
        # derivatives because they have copies of ``self.search_fields``.
        self.search_fields.append(self.derivative_choice)

    def get_query_set(self, base_query=None):
        """Returns all model instances matching the search.  This is heavily changed
        from :py:meth:`SearchTreeNode.get_query_set`.  By and large it only
        “or”s the returned search results from the derivatives.

        :param base_query: the query set to be used as the starting point of the
            query, see :py:meth:`SearchTreeNode.get_query_set`

        :type base_query: QuerySet

        :return:
          the search results

        :rtype: QuerySet
        """
        result = base_query if base_query is not None else self.model_class.objects
        selected_derivative = self.derivative_choice.form.cleaned_data["derivative"]
        if selected_derivative:
            selected_derivatives = [derivative for derivative in self.derivatives
                                    if derivative.model_class.__name__ == selected_derivative]
        else:
            selected_derivatives = self.derivatives
        assert selected_derivatives
        Q_expression = None
        for node in selected_derivatives:
            current_Q = Q(pk__in=node.get_query_set())
            if Q_expression:
                Q_expression |= current_Q
            else:
                Q_expression = current_Q
        result = result.filter(Q_expression).distinct()
        return result.only("pk")


class DetailsSearchTreeNode(SearchTreeNode):
    """Class representing a search tree node which represents a model which is
    extended with a “details” model through a O2O relationship.  If you use an
    ordinary `SearchTreeNode` for this, you get an extra nesting level because
    the user first have to choose the details model, and then he gets its
    fields.  By using this class however, the details model is merged with its
    main model – at least as far as searching is concerned.

    Note that this class is not applicable if both the main model and its
    datails model have a related model in common.  This cannot be untangled, so
    then you have to bite the bullet and use `SearchTreeNode` instead.

    Also note that there must be a details instance for every main instance.
    You must assure elsewhere that there is no “dangling” main model instance.
    """

    def __init__(self, model_class, related_models, search_fields, details_model_attribute):
        """Class constructor.

        :param model_class: the model class associated with this node
        :param related_models: see the description of the instance variable of
            the same name
        :param search_fields: see the description of the instance variable of
            the same name; they don't contain a form because their `parse_data`
            method has not been called yet
        :param details_model_attribute: attribute name which represents the O2O
            relationship to the details model

        :type model_class: class (decendant of models.Model)
        :type related_models: dict mapping class (decendant of models.Model) to
          str
        :type search_fields: list of `SearchField`
        :type details_model_attribute: str
        """
        super(DetailsSearchTreeNode, self).__init__(model_class, related_models, search_fields)
        self.details_model_attribute = details_model_attribute
        self.details_model_class = getattr(model_class, details_model_attribute).related.model
        self.details_node = self.details_model_class.get_search_tree_node()
        self.related_models.update(self.details_node.related_models)
        self.search_fields.extend(self.details_node.search_fields)

    def get_query_set(self, base_query=None):
        # The basic idea here is the following: The search fields and the
        # related models of the details model were merged with the ones of the
        # main model.  During `parse_data`, they are read in as if they were
        # part of the main model.
        #
        # Here, however, we have to untangle this.  The search fields of the
        # details model are simply skipped over here – the details model still
        # has its own references to them and can use them after all.  The
        # children which actually belong to the details model are skipped over
        # and injected into the details model's node.  Finally, this node is
        # used in the query as a filter.
        result = base_query if base_query is not None else self.model_class.objects
        kwargs = {}
        for search_field in (field for field in self.search_fields if field not in self.details_node.search_fields):
            values = search_field.get_values()
            if values:
                kwargs.update(values)
        result = result.filter(**kwargs)
        for __, node in self.children:
            if node:
                if node.model_class not in self.details_node.related_models:
                    name = self.related_models[node.model_class] + "__pk__in"
                    result = result.filter(**{name: node.get_query_set()})
                else:
                    self.details_node.children.append((None, node))
        result = result.filter(pk__in=self.details_node.get_query_set())
        return result.only("pk")


_ = ugettext
