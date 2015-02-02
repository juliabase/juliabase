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

"""Support for classed-based add and edit views for processes.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from django.db.models import Max
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.utils.text import capfirst
from django.utils.safestring import mark_safe
from django.utils.encoding import force_text
import django.forms as forms
from django.forms.util import ValidationError
from jb_common.utils.base import camel_case_to_underscores, is_json_requested, format_enumeration, int_or_zero
from samples import permissions
from . import forms as utils
from .feed import Reporter
from .base import successful_response, extract_preset_sample, remove_samples_from_my_samples


__all__ = ("ProcessView", "ProcessMultipleSamplesView", "RemoveFromMySamplesMixin", "SubprocessForm", "SubprocessesMixin",
           "DepositionView", "DepositionMultipleTypeView")


class ProcessWithoutSamplesView(TemplateView):
    """Abstract base class for the classed-based views.  It deals only with the
    process per se, and in partuclar, with no samples associated with this
    process.  This is done in the concrete derived classes
    :py:class:`~samples.utils.views.ProcessView` (one sample) and
    :py:class:`ProcessMultipleSamplesView` (multiple samples).  So, you should
    never instantiate this one.

    The methods that you most likely want to redefine in you own concrete class
    are, with decreasing probability:

    - :py:meth:`is_referentially_valid`
    - :py:meth:`save_to_database`
    - :py:meth:`get_next_id`
    - :py:meth:`build_forms`
    - :py:meth:`get_title`
    - :py:meth:`get_context_data`

    Note that for :py:meth:`is_referentially_valid`,
    :py:meth:`save_to_database`, :py:meth:`build_forms`, and
    :py:meth:`get_context_data`, it is necessary to call the inherited method.

    Since you connect forms with the view class, the view class expects certain
    constructor signatures of the forms.  As for the process model form, it
    must accept the logged-in user as the first argument.  This is the case for
    :py:class:`~samples.utils.views.ProcessForm` and
    :py:class:`~samples.utils.views.DepositionForm`, so this should not be a
    problem.  The derived class (see below) may impose constrains on their
    external forms either.

    :ivar form_class: The model form class of the process of this view.

    :ivar model: The model class of the view.  If not given, it is derived from
      the process form class.

    :ivar class_name: The name of the model class,
      e.g. ``"clustertooldeposition"``.

    :ivar process: The process instance this view is about.  If we are about to
      add a new process, this is ``None`` until the respective form is saved.

    :ivar forms: A dictionary mapping template context names to forms, or lists
      of forms.  Mandatory keys in this dictionary are ``"process"`` and
      ``"edit_description"``.  (Derived classes add ``"sample"``,
      ``"samples"``, ``"remove_from_my_samples"``, ``"layers"``, etc.)

    :ivar data: The POST data if we have a POST request, or ``None`` otherwise.

    :ivar id: The ID of the process to edit, or ``None`` if we are about to add
      a new one.  This is the recommended way to distinguish between editing
      and adding.

    :ivar preset_sample: The sample with which the process should be connected
      by default.  May be ``None``.

    :ivar request: The current request object.  This is inherited from Django's
      view classes.

    :ivar template_name: The file name of the rendering template, with the same
      path syntax as in the ``render()`` function.

    :ivar identifying_field: The name of the field in the process which is the
      poor man's primary key for this process, e.g. the deposition number.  It
      is taken from the model class.
    """
    model = None

    def __init__(self, **kwargs):
        self.model = self.model or self.form_class.Meta.model
        self.class_name = camel_case_to_underscores(self.model.__name__)
        self.template_name = "samples/edit_{}.html".format(self.class_name)
        super(ProcessWithoutSamplesView, self).__init__(**kwargs)
        self.forms = {}

    def startup(self):
        """Fetch the process to-be-edited from the database and check permissions.
        This method has no parameters and no return values, ``self`` is
        modified in-situ.
        """
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
        """Gets the next identifying value for the process class.  In its default
        implementation, it just takes the maximal existing value and adds 1.
        This needs to be overridden if the identifying field is non-numeric.

        :Return:
          The next untaken of the identifying field, e.g. the next free
          depostion number.

        :rtype: object
        """
        return (self.model.objects.aggregate(Max(self.identifying_field))[self.identifying_field + "__max"] or 0) + 1

    def build_forms(self):
        """Fills the :py:attr:`forms` dictionary with the forms, or lists of them.  In
        this base class, we only add ``"process"`` itself and
        ``"edit_description"``.  Note that the dictionary key is later used in
        the template as context variable.

        This method has no parameters and no return values, ``self`` is
        modified in-situ.  It is good habit to check for a key before setting
        it, allowing derived methods to set it themselves without doing double
        work.
        """
        if "process" not in self.forms:
            initial = {}
            if not self.id:
                next_id = self.get_next_id()
                if next_id:
                    initial[self.identifying_field] = next_id
            self.forms["process"] = self.form_class(self.request.user, self.data, instance=self.process, initial=initial)
        self.forms["edit_description"] = utils.EditDescriptionForm(self.data) if self.id else None

    def _check_validity(self, forms):
        """Helper for :py:meth:`is_all_valid` for allowing recursion through
        nested lists of forms.
        """
        all_valid = True
        for form in forms:
            if isinstance(form, (list, tuple)):
                all_valid = self._check_validity(form) and all_valid
            elif form is not None:
                all_valid = (not form.is_bound or form.is_valid()) and all_valid
        return all_valid
        
    def is_all_valid(self):
        """Checks whether all forms are valid.  Unbound forms – which may occur also in
        POST requests – are not checked.  Moreover, this method guarantees that
        the :py:meth:`is_valid` method of every bound form is called in order
        to collect all error messages.

        :Return:
          whether all forms are valid

        :rtype: bool
        """
        return self._check_validity(self.forms.values())

    def is_referentially_valid(self):
        """Checks whether the data of all forms is consistent with each other
        and with the database.  This is the partner of :py:meth:`is_all_valid`
        but checks the inter-relations of data.

        This method is frequently overriden in concrete view classes.

        Note that a ``True`` here does not imply a ``True`` from
        :py:meth:`is_all_valid`.  Both methods are independent of each other.
        In particular, you must check the validity of froms that you use here.

        :Return:
          whether the data submitted to the view is valid

        :rtype: bool
        """
        return True

    def save_to_database(self):
        """Saves the data to the database.

        :Return:
          the saved process instance

        :rtype: `samples.models.PhysicalProcess`
        """
        process = self.forms["process"].save()
        return process

    def get(self, request, *args, **kwargs):
        """Processes a GET request.  This method is part of the Django API for
        class-based views.

        :param request: the HTTP request object

        :type request: ``django.http.HttpRequest``

        :Return:
          the HTTP response

        :rtype: ``django.http.HttpResponse``
        """
        self.startup()
        self.build_forms()
        return super(ProcessWithoutSamplesView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Processes a POST request.  This method is part of the Django API for
        class-based views.

        :param request: the HTTP request object

        :type request: ``django.http.HttpRequest``

        :Return:
          the HTTP response

        :rtype: ``django.http.HttpResponse``
        """
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
                _("{process} was successfully added to the database.").format(process=self.process)
            return successful_response(request, success_report, json_response=self.process.pk)
        else:
            return super(ProcessWithoutSamplesView, self).get(request, *args, **kwargs)

    def get_title(self):
        """Creates the title of the response.  This is used in the ``<title>``
        tag and the ``<h1>`` tag at the top of the page.

        :Return:
          the title of the response

        :rtype: unicode
        """
        return capfirst(_("edit {process}").format(process=self.process)) if self.id else \
            capfirst(_("add {class_name}").format(class_name=self.model._meta.verbose_name))

    def get_context_data(self, **kwargs):
        """Generates the template context.  In particular, we inject the forms and the
        title here into the context.  This method is part of the official
        Django API.

        :Return:
          the context dict

        :rtype: dict
        """
        context = {}
        context["title"] = self.get_title()
        context.update(kwargs)
        context.update(self.forms)
        return super(ProcessWithoutSamplesView, self).get_context_data(**context)

    @classmethod
    def as_view(cls, **initkwargs):
        """Return the callable for the URL patterns.  This is part of the official
        Django API.  We override it to add a login check.
        """
        view = super(ProcessWithoutSamplesView, cls).as_view(**initkwargs)
        return login_required(view)


class ProcessView(ProcessWithoutSamplesView):
    """View class for physical processes with one sample each.  The HTML form for
    the sample is called ``sample`` in the template.  Typical usage can be very
    short::

        from samples.utils.views import ProcessForm, ProcessView

        class LayerThicknessForm(ProcessForm):
            class Meta:
                model = LayerThicknessMeasurement
                fields = "__all__"

        class EditView(ProcessView):
            form_class = LayerThicknessForm
    """

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
    """View class for physical processes with one or more samples each.  The HTML
    form for the sample list is called ``samples`` in the template.  The usage
    is analogous to :py:class:`~samples.utils.views.ProcessView`.
    """

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
    """Mixin for views that like to offer a “Remove from my samples” button.  In
    the template, they may add the following code::

        {{ remove_from_my_samples.as_p }}

    This mixin must come before the main view class in the list of parents.
    """

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
    number = forms.IntegerField(label=_("number of subprocesses"), min_value=1, max_value=100, required=False)


class SubprocessForm(forms.ModelForm):
    """Model form class for subprocesses and deposition layers.  Its only purpose
    is to eat up the ``view`` parameter to the constructor so that you need not
    redefine the constructor every time.
    """
    def __init__(self, view, *args, **kwargs):
        super(SubprocessForm, self).__init__(*args, **kwargs)
        self.view = view


class SubprocessesMixin(ProcessWithoutSamplesView):
    """Mixing for views that represent processes with subprocesses.  Have a look at
    :py:mod:`institute.views.samples.solarsimulator_measurement` for an
    example.  For this to work, you must define the followin additional class
    variables:

    - :py:attr:`subform_class`: the model form class for the subprocesses
    - :py:attr:`process_field`: the name of the field of the parent process in
      the subprocess model
    - :py:attr:`subprocess_field`: the ``related_name`` parameter in the field
      of the parent process in the subprocess model

    You should derive the model form class of the subprocess from
    :py:class:`~samples.utils.views.SubprocessForm`.  This is not mandatory but
    convenient, see there.

    In the template, the forms of the subprocesses are available in a list
    called ``subprocesses``.  Furthermore, you should include

    ::

        {{ number.as_p }}

    in the template so that the user can set the number of subprocesses.

    This mixin must come before the main view class in the list of parents.
    """

    sub_model = None

    def __init__(self, **kwargs):
        super(SubprocessesMixin, self).__init__(**kwargs)
        self.sub_model = self.sub_model or self.subform_class.Meta.model
        
    def build_forms(self):
        super(SubprocessesMixin, self).build_forms()
        if self.id:
            subprocesses = getattr(self.process, self.subprocess_field)
            if not self.sub_model._meta.ordering:
                subprocesses = subprocesses.order_by("id")
        else:
            subprocesses = self.sub_model.objects.none()
        if self.request.method == "POST":
            indices = utils.collect_subform_indices(self.data)
            self.forms["number"] = NumberForm(self.data)
            if self.forms["number"].is_valid():
                new_number_of_forms = self.forms["number"].cleaned_data["number"] or len(indices)
                indices = indices[:new_number_of_forms]
            else:
                new_number_of_forms = len(indices)
            instances = list(subprocesses.all()) + (len(indices) - subprocesses.count()) * [None]
            self.forms["subprocesses"] = [self.subform_class(self, self.data, prefix=str(index), instance=instance)
                                          for index, instance in zip(indices, instances)]
            number_of_new_forms = new_number_of_forms - len(indices)
            if number_of_new_forms > 0:
                self.forms["subprocesses"].extend([self.subform_class(self, prefix=str(index))
                                                   for index in range(max(indices or [-1]) + 1,
                                                                      max(indices or [-1]) + 1 + number_of_new_forms)])
        else:
            self.forms["number"] = NumberForm(initial={"number": subprocesses.count()})
            self.forms["subprocesses"] = [self.subform_class(self, prefix=str(index), instance=subprocess)
                                          for index, subprocess in enumerate(subprocesses.all())]

    def is_referentially_valid(self):
        referentially_valid = super(SubprocessesMixin, self).is_referentially_valid()
        if not self.forms["subprocesses"]:
            self.forms["process"].add_error(None, _("No subprocesses given."))
            referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        process = super(SubprocessesMixin, self).save_to_database()
        getattr(process, self.subprocess_field).all().delete()
        for form in self.forms["subprocesses"]:
            subprocess = form.save(commit=False)
            setattr(subprocess, self.process_field, process)
            subprocess.save()
        return process


class ChangeLayerForm(forms.Form):
    """Form for manipulating a layer.  Duplicating it (appending the
    duplicate), deleting it, and moving it up- or downwards.
    """
    duplicate_this_layer = forms.BooleanField(label=_("duplicate this layer"), required=False)
    remove_this_layer = forms.BooleanField(label=_("remove this layer"), required=False)
    move_this_layer = forms.ChoiceField(label=_("move this layer"), required=False,
                                        choices=(("", "---------"), ("up", _("up")), ("down", _("down"))))

    def clean(self):
        cleaned_data = super(ChangeLayerForm, self).clean()
        operations = 0
        if cleaned_data["duplicate_this_layer"]:
            operations += 1
        if cleaned_data["remove_this_layer"]:
            operations += 1
        if cleaned_data.get("move_this_layer"):
            operations += 1
        if operations > 1:
            raise ValidationError(_("You can't duplicate, move, or remove a layer at the same time."))
        return cleaned_data


class AddMyLayersForm(forms.Form):
    """Form for adding a pre-defined layer from the “My Layers” list.  At the
    same time, this serves as the base class for other add-layers forms since
    adding “My Layers” should be *always* possible.
    """
    my_layer_to_be_added = forms.ChoiceField(label=_("Nickname of My Layer to be added"), required=False)

    def __init__(self, view, data=None, **kwargs):
        super(AddMyLayersForm, self).__init__(data, **kwargs)
        self.fields["my_layer_to_be_added"].choices = utils.get_my_layers(view.request.user.samples_user_details, view.model)
        self.model = view.model

    def clean_my_layer_to_be_added(self):
        nickname = self.cleaned_data["my_layer_to_be_added"]
        if nickname and "-" in nickname:
            process_id, layer_number = self.cleaned_data["my_layer_to_be_added"].split("-")
            process_id, layer_number = int(process_id), int(layer_number)
            try:
                deposition = self.model.objects.get(pk=process_id)
            except self.model.DoesNotExist:
                pass
            else:
                layer_query = deposition.layers.filter(number=layer_number)
                if layer_query.count() == 1:
                    return layer_query.values()[0]

    def change_structure(self, structure_changed, new_layers):
        """Apply the changes introduced by adding layers to the data structures of the
        caller.  This caller is the :py:meth:`_change_structure` method of a
        view class, which in turn is usually called shortly before validating
        all forms.

        :param structure_changed: whether the caller has already performed
          layer-list-changing operations, e.g. deleting of a layer.

        :param new_layers: a list of the layers after the structure changes.
          It is a list of tuples with three elements, a string denoting the
          change, a dict with the initial layer data, and possibly a
          :py:class:`ChangeLayerForm`.  The latter is optional, however, and
          not added here.

        :type structure_changed: bool
        :type new_layers: list of (str, dict, ChangeLayerForm) or (str, dict)

        :Return:
          the updated values for ``structure_changed`` and ``new_layers``

        :rtype: bool, list of (str, dict, ChangeLayerForm) or (str, dict)
        """
        my_layer_data = self.cleaned_data["my_layer_to_be_added"]
        if my_layer_data is not None:
            new_layers.append(("new", my_layer_data))
            structure_changed = True
        return structure_changed, new_layers


class AddLayersForm(AddMyLayersForm):
    """Add-layers form with additional number of layers to add.
    """
    number_of_layers_to_add = forms.IntegerField(label=_("Number of layers to be added"), min_value=0, max_value=10,
                                                 required=False)

    def __init__(self, view, data=None, **kwargs):
        super(AddLayersForm, self).__init__(view, data, **kwargs)
        self.fields["number_of_layers_to_add"].widget.attrs["size"] = "5"
        self.model = view.model

    def clean_number_of_layers_to_add(self):
        return int_or_zero(self.cleaned_data["number_of_layers_to_add"])

    def change_structure(self, structure_changed, new_layers):
        structure_changed, new_layers = super(AddLayersForm, self).change_structure(structure_changed, new_layers)
        for i in range(self.cleaned_data["number_of_layers_to_add"]):
            new_layers.append(("new", {}))
            structure_changed = True
        return structure_changed, new_layers


class DepositionView(ProcessWithoutSamplesView):
    """View class for depositions.  The layers of the deposition must always be of
    the same type.  If they are now, you must use
    :py:class:`DepositionMultipleTypeView` instead.  Additionally to
    :py:attr:`form_class`, you must set the :py:attr:`layer_form_class` class
    variable to the form class to be used for the layers.

    The layer form should be a subclass of :py:class:`~samples.utils.views.SubprocessForm`.
    """
    add_layers_form_class = AddLayersForm

    def _change_structure(self):
        """Apply any layer-based rearrangements the user has requested.  This
        is layer duplication, order changes, appending of layers, and deletion.

        The method has two parts: First, the changes are collected in a data
        structure called ``new_layers``.  Then, we walk through ``new_layers``
        and build a new list ``self.forms["layers"]`` from it.

        ``new_layers`` is a list of small lists.  Every small list has a string
        as its zeroth element which may be ``"original"``, ``"duplicate"``, or
        ``"new"``, denoting the origin of that layer form.  The remainding
        elements are parameters: the (old) layer and change-layer form for
        ``"original"``; the source layer form for ``"duplicate"``; and the
        initial layer form data for ``"new"``.

        Of course, the new layer forms are not validated.  Therefore,
        `__is_all_valid` is called *after* this routine in `save_to_database`.

        Note that – as usual – the numbers of depositions and layers are called
        *number*, whereas the internal numbers used as prefixes in the HTML
        names are called *indices*.  The index (and thus prefix) of a layer
        form does never change (in contrast to the 6-chamber deposition, see
        :py:func:`samples.views.form_utils.normalize_prefixes`), not even
        across many “post cycles”.  Only the layer numbers are used for
        determining the order of layers.

        :return:
          whether the structure was changed in any way.

        :rtype: bool
        """
        structure_changed = False
        new_layers = [["original", layer_form, change_layer_form]
                      for layer_form, change_layer_form in zip(self.forms["layers"], self.forms["change_layers"])]

        # Move layers
        for i in range(len(new_layers)):
            layer_form, change_layer_form = new_layers[i][1:3]
            if change_layer_form.is_valid():
                movement = change_layer_form.cleaned_data["move_this_layer"]
                if movement:
                    new_layers[i][2] = ChangeLayerForm(prefix=layer_form.prefix)
                    structure_changed = True
                    if movement == "up" and i > 0:
                        temp = new_layers[i - 1]
                        new_layers[i - 1] = new_layers[i]
                        new_layers[i] = temp
                    elif movement == "down" and i < len(new_layers) - 1:
                        temp = new_layers[i]
                        new_layers[i] = new_layers[i + 1]
                        new_layers[i + 1] = temp

        # Duplicate layers
        for i in range(len(new_layers)):
            layer_form, change_layer_form = new_layers[i][1:3]
            if layer_form.is_valid() and \
                    change_layer_form.is_valid() and change_layer_form.cleaned_data["duplicate_this_layer"]:
                new_layers.append(("duplicate", layer_form))
                new_layers[i][2] = ChangeLayerForm(prefix=layer_form.prefix)
                structure_changed = True

        # Add layers
        if self.forms["add_layers"].is_valid():
            structure_changed, new_layers = self.forms["add_layers"].change_structure(structure_changed, new_layers)
            self.forms["add_layers"] = self.add_layers_form_class(self)

        # Delete layers
        for i in range(len(new_layers) - 1, -1, -1):
            if len(new_layers[i]) == 3:
                change_layer_form = new_layers[i][2]
                if change_layer_form.is_valid() and change_layer_form.cleaned_data["remove_this_layer"]:
                    del new_layers[i]
                    structure_changed = True

        self._apply_changes(new_layers)
        return structure_changed

    def _apply_changes(self, new_layers):
        """Applies the collected changes in the layer forms by building a new list of
        layer forms.  This method abstracts something that needs to be made
        differently in
        :py:class:`samples.utils.views.DepositionMultipleTypeView`.

        :params new_layers: the list of the new layers, see
          :py:meth:`AddMyLayersForm.change_structure`.

        :type new_layers: list of (str, dict, ChangeLayerForm) or (str, dict)
        """
        next_layer_number = 1
        old_prefixes = [int(layer_form.prefix) for layer_form in self.forms["layers"] if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.forms["layers"] = []
        self.forms["change_layers"] = []
        for new_layer in new_layers:
            if new_layer[0] == "original":
                post_data = self.data.copy() if self.data is not None else {}
                prefix = new_layer[1].prefix
                post_data[prefix + "-number"] = next_layer_number
                next_layer_number += 1
                self.forms["layers"].append(self.layer_form_class(self, post_data, prefix=prefix))
                self.forms["change_layers"].append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = next_layer_number
                    next_layer_number += 1
                    self.forms["layers"].append(self.layer_form_class(self, initial=layer_data, prefix=str(next_prefix)))
                    self.forms["change_layers"].append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                initial = new_layer[1]
                initial["number"] = next_layer_number
                self.forms["layers"].append(self.layer_form_class(self, initial=initial, prefix=str(next_prefix)))
                self.forms["change_layers"].append(ChangeLayerForm(prefix=str(next_prefix)))
                next_layer_number += 1
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])

    def get_layer_form(self, prefix):
        """Returns the layer form with the given prefix.  This method abstracts
        something that needs to be made differently in
        :py:class:`samples.utils.views.DepositionMultipleTypeView`.

        :param prefix: the prefix of the resulting form

        :type prefix: unicode

        :Return:
          the layer form

        :rtype: :py:class:`~samples.utils.views.SubprocessForm`
        """
        return self.layer_form_class(self, self.data, prefix=prefix)

    def _read_layer_forms(self, source_deposition):
        """Generate a set of layer forms from database data.  Note that the layers are
        not returned – instead, they are written directly into
        ``self.layer_forms``.

        :param source_deposition: the deposition from which the layers should
            be taken.  Note that this may be the deposition which is currently
            edited, or the deposition which is duplicated to create a new
            deposition.

        :type source_deposition: `samples.models.Depositions`
        :type destination_deposition_number: unicode
        """
        self.forms["layers"] = [self.layer_form_class(self, prefix=str(layer_index), instance=layer,
                                                      initial={"number": layer_index + 1})
                                for layer_index, layer in enumerate(source_deposition.layers.all())]

    def build_forms(self):
        if "samples" not in self.forms:
            self.forms["samples"] = utils.DepositionSamplesForm(self.request.user, self.process, self.preset_sample,
                                                                self.data)
        self.forms["add_layers"] = self.add_layers_form_class(self, self.data)
        if self.request.method == "POST":
            indices = utils.collect_subform_indices(self.data)
            self.forms["layers"] = [self.get_layer_form(prefix=str(layer_index)) for layer_index in indices]
            self.forms["change_layers"] = [ChangeLayerForm(self.data, prefix=str(change_layer_index))
                                           for change_layer_index in indices]
        else:
            copy_from = self.request.GET.get("copy_from")
            if not self.id and copy_from:
                # Duplication of a deposition
                source_deposition_query = self.model.objects.filter(number=copy_from)
                if source_deposition_query.count() == 1:
                    deposition_data = source_deposition_query.values()[0]
                    deposition_data["timestamp"] = datetime.datetime.now()
                    deposition_data["timestamp_inaccuracy"] = 0
                    deposition_data["operator"] = self.request.user.pk
                    deposition_data["number"] = self.get_next_id()
                    self.forms["process"] = self.form_class(self.request.user, initial=deposition_data)
                    self._read_layer_forms(source_deposition_query[0])
            if "layers" not in self.forms:
                if self.id:
                    # Normal edit of existing deposition
                    self._read_layer_forms(self.process)
                else:
                    # New deposition, or duplication has failed
                    self.forms["layers"] = []
            self.forms["change_layers"] = [ChangeLayerForm(prefix=str(index)) for index in range(len(self.forms["layers"]))]
        super(DepositionView, self).build_forms()

    def is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.  This
        function calls the ``is_valid()`` method of all forms, even if one of
        them returns ``False`` (and makes the return value clear prematurely).

        :return:
          whether all forms are valid.

        :rtype: bool
        """
        all_valid = not self._change_structure() if not is_json_requested(self.request) else True
        all_valid = super(DepositionView, self).is_all_valid() and all_valid
        return all_valid

    def is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.  For example, no layer number must occur twice, and the
        deposition number must not exist within the database.

        Note that we test many situations here that cannot be achieved with
        using the browser because all number fields are read-only and thus
        inherently referentially valid.  However, the remote client (or a
        manipulated HTTP client) may be used in a malicious way, thus we have
        to test for *all* cases.

        :return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = super(DepositionView, self).is_referentially_valid()
        if not self.forms["layers"]:
            self.forms["process"].add_error(None, _("No layers given."))
            referentially_valid = False
        if self.forms["process"].is_valid():
            if self.forms["samples"].is_valid():
                dead_samples = utils.dead_samples(self.forms["samples"].cleaned_data["sample_list"],
                                                  self.forms["process"].cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(
                        "The sample {samples} is already dead at this time.",
                        "The samples {samples} are already dead at this time.", len(dead_samples)).format(
                        samples=format_enumeration([sample.name for sample in dead_samples]))
                    self.forms["process"].add_error("timestamp", error_message)
                    referentially_valid = False
        return referentially_valid

    def get_context_data(self, **kwargs):
        context = super(DepositionView, self).get_context_data(**kwargs)
        context["layers_and_change_layers"] = list(zip(self.forms["layers"], self.forms["change_layers"]))
        return context

    def save_to_database(self):
        """Apply all layer changes, check the whole validity of the data, and
        save the forms to the database.  Only the deposition is just updated if
        it already existed.  However, the layers are completely deleted and
        re-constructed from scratch.

        :return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `institute.models.FiveChamberDeposition` or NoneType
        """
        deposition = super(DepositionView, self).save_to_database()
        if not self.id:
            # Change sample list only for *new* depositions
            deposition.samples = self.forms["samples"].cleaned_data["sample_list"]
        deposition.layers.all().delete()
        for layer_form in self.forms["layers"]:
            layer = layer_form.save(commit=False)
            layer.deposition = deposition
            layer.save()
        return deposition


class SimpleRadioSelectRenderer(forms.widgets.RadioFieldRenderer):
    def render(self):
        return mark_safe("""<ul class="radio-select">\n{0}\n</ul>""".format("\n".join(
                    "<li>{0}</li>".format(force_text(w)) for w in self)))


class AddMultipleTypeLayersForm(AddMyLayersForm):
    """Form for adding a new layer in case of layers of different types.
    """
    layer_to_be_added = forms.ChoiceField(label=_("Layer to be added"), required=False,
                                          widget=forms.RadioSelect(renderer=SimpleRadioSelectRenderer))

    def __init__(self, view, data=None, **kwargs):
        super(AddMultipleTypeLayersForm, self).__init__(view, data, **kwargs)
        # Translators: No further layer
        self.fields["layer_to_be_added"].choices = view.new_layer_choices + (("", _("none")),)
        self.new_layer_choices = view.new_layer_choices

    def change_structure(self, structure_changed, new_layers):
        structure_changed, new_layers = super(AddMultipleTypeLayersForm, self).change_structure(structure_changed, new_layers)
        new_layer_type = self.cleaned_data["layer_to_be_added"]
        if new_layer_type:
            new_layers.append(("new " + new_layer_type, {}))
            structure_changed = True
        return structure_changed, new_layers


class DepositionMultipleTypeView(DepositionView):
    """View class for depositions the layers of which are of different types (i.e.,
    different models).  You can see it in action in the module
    :py:mod:`institute.views.samples.cluster_tool_deposition`.  Additionally to
    the class variable :py:attr:`form_class`, you must set:

    :ivar layer_form_classes: This is a tuple of the form classes for the layers
    
    :ivar short_labels: *(optional)* This is a dict mapping a layer form class
      to a concise name of that layer type.  It is used in the selection widget
      of the add-layer form.

    :type layer_form_classes: tuple of
      :py:class:`~samples.utils.views.SubprocessForm`
    :type short_labels: dict mapping
      :py:class:`~samples.utils.views.SubprocessForm` to unicode.
    """
    model = None
    form_class = None
    layer_form_classes = ()
    short_labels = None
    add_layers_form_class = AddMultipleTypeLayersForm

    class LayerForm(forms.Form):
        """Dummy form class for detecting the actual layer type.  It is used
        only in `from_post_data`."""
        layer_type = forms.CharField()

    def __init__(self, **kwargs):
        super(DepositionMultipleTypeView, self).__init__(**kwargs)
        if not self.short_labels:
            self.short_labels = {cls: cls.Meta.model._meta.verbose_name for cls in self.layer_form_classes}
        self.new_layer_choices = tuple((cls.Meta.model.__name__.lower(), self.short_labels[cls])
                                       for cls in self.layer_form_classes)
        self.layer_types = {cls.Meta.model.__name__.lower(): cls for cls in self.layer_form_classes}

    def _read_layer_forms(self, source_deposition):
        self.forms["layers"] = []
        for index, layer in enumerate(source_deposition.layers.all()):
            layer = layer.actual_instance
            LayerFormClass = self.layer_types[layer.__class__.__name__.lower()]
            self.forms["layers"].append(
                LayerFormClass(self, prefix=str(index), instance=layer, initial={"number": index + 1}))

    def get_layer_form(self, prefix):
        layer_form = self.LayerForm(self.data, prefix=prefix)
        LayerFormClass = self.layer_form_classes[0]   # default
        if layer_form.is_valid():
            layer_type = layer_form.cleaned_data["layer_type"]
            try:
                LayerFormClass = self.layer_types[layer_type]
            except KeyError:
                pass
        return LayerFormClass(self, self.data, prefix=prefix)

    def _apply_changes(self, new_layers):
        old_prefixes = [int(layer_form.prefix) for layer_form in self.forms["layers"] if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.forms["layers"] = []
        self.forms["change_layers"] = []
        for i, new_layer in enumerate(new_layers):
            if new_layer[0] == "original":
                original_layer = new_layer[1]
                LayerFormClass = self.layer_types[original_layer.type]
                post_data = self.data.copy() if self.data else {}
                prefix = new_layer[1].prefix
                post_data[prefix + "-number"] = str(i + 1)
                self.forms["layers"].append(LayerFormClass(self, post_data, prefix=prefix))
                self.forms["change_layers"].append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    LayerFormClass = self.layer_types[original_layer.type]
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = i + 1
                    self.forms["layers"].append(LayerFormClass(self, initial=layer_data, prefix=str(next_prefix)))
                    self.forms["change_layers"].append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                # New MyLayer
                initial = {}
                id_ = new_layer[1]["id"]
                layer_class = models.Layer.objects.get(id=id_).content_type.model_class()
                LayerFormClass = self.layer_types[layer_class.__name__.lower()]
                initial = layer_class.objects.filter(id=id_).values()[0]
                initial["number"] = i + 1
                self.forms["layers"].append(LayerFormClass(self, initial=initial, prefix=str(next_prefix)))
                self.forms["change_layers"].append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            elif new_layer[0].startswith("new "):
                LayerFormClass = self.layer_types[new_layer[0][len("new "):]]
                self.forms["layers"].append(LayerFormClass(self, initial={"number": "{0}".format(i + 1)},
                                                           prefix=str(next_prefix)))
                self.forms["change_layers"].append(ChangeLayerForm(prefix=str(next_prefix)))
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])


_ = ugettext
