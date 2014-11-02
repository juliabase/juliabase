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


"""
"""

from __future__ import absolute_import, unicode_literals

import re, datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from samples import models
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext, ungettext
from jb_common.utils import is_json_requested
from samples.views import utils, feed_utils
from jb_institute.views import form_utils
import jb_institute.models as institute_models


class DepositionForm(form_utils.ProcessForm):
    """Model form for the deposition main data.  I only overwrite ``operator``
    in order to have full real names.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))

    def __init__(self, user, data=None, **kwargs):
        """Class constructor just for changing the appearance of the number
        field."""
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"style": "font-size: large", "size": "8"})
        deposition = kwargs.get("instance")
        self.fields["operator"].set_operator(deposition.operator if deposition else user, user.is_staff)
        self.fields["operator"].initial = deposition.operator.pk if deposition else user.pk
        self.already_finished = deposition and deposition.finished
        if self.already_finished:
            self.fixed_previous_deposition_number = deposition.number
            self.fields["number"].widget.attrs.update({"readonly": "readonly"})
        else:
            self.fixed_previous_deposition_number = None

    def clean_number(self):
        number = self.cleaned_data["number"]
        if self.fixed_previous_deposition_number and self.fixed_previous_deposition_number != number:
            raise ValidationError(_("The deposition number must not be changed."))
        number = form_utils.clean_deposition_number_field(number, "S")
        if (not self.fixed_previous_deposition_number or self.fixed_previous_deposition_number != number) and \
                models.Deposition.objects.filter(number=number).exists():
            raise ValidationError(_("This deposition number exists already."))
        return number

    def clean(self):
        _ = ugettext
        if "number" in self.cleaned_data and "timestamp" in self.cleaned_data:
            if int(self.cleaned_data["number"][:2]) != self.cleaned_data["timestamp"].year % 100:
                self.add_error("number", _("The first two digits must match the year of the deposition."))
        return self.cleaned_data

    class Meta:
        model = institute_models.FiveChamberDeposition
        exclude = ("external_operator",)


class LayerForm(forms.ModelForm):
    """Model form for a single layer.
    """
    def __init__(self, *args, **kwargs):
        """Form constructor.  I only tweak the HTML layout slightly, and I set
        the initial date to today for fresh layers.
        """
        if "instance" not in kwargs:
            # Note that ``initial`` has higher priority than ``instance`` in
            # model forms.
            initial = kwargs.get("initial", {})
            initial["date"] = datetime.date.today()
            kwargs["initial"] = initial
        super(LayerForm, self).__init__(*args, **kwargs)
        self.fields["number"].widget.attrs.update({"readonly": "readonly", "size": "5", "style": "font-size: large"})
        for fieldname in ["date", "sih4", "h2", ]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        self.fields["temperature_1"].widget.attrs["size"] = "5"
        self.fields["temperature_2"].widget.attrs["size"] = "5"

    def clean_date(self):
        return form_utils.clean_timestamp_field(self.cleaned_data["date"])

    class Meta:
        model = institute_models.FiveChamberLayer
        exclude = ("deposition",)


class ChangeLayerForm(forms.Form):
    """Form for manipulating a layer.  Duplicating it (appending the
    duplicate), deleting it, and moving it up- or downwards.
    """
    _ = ugettext_lazy
    duplicate_this_layer = forms.BooleanField(label=_("duplicate this layer"), required=False)
    remove_this_layer = forms.BooleanField(label=_("remove this layer"), required=False)
    move_this_layer = forms.ChoiceField(label=_("move this layer"), required=False,
                                        choices=(("", "---------"), ("up", _("up")), ("down", _("down"))))

    def clean(self):
        _ = ugettext
        operations = 0
        if self.cleaned_data["duplicate_this_layer"]:
            operations += 1
        if self.cleaned_data["remove_this_layer"]:
            operations += 1
        if self.cleaned_data.get("move_this_layer"):
            operations += 1
        if operations > 1:
            raise ValidationError(_("You can't duplicate, move, or remove a layer at the same time."))
        return self.cleaned_data


class FormSet(object):
    """Class for holding all forms of the 5-chamber deposition views, and for
    all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `institute_models.FiveChamberDeposition` or ``NoneType``
    """
    deposition_number_pattern = re.compile(r"(?P<prefix>\d\dS-)(?P<number>\d+)$")

    def __init__(self, request, deposition_number):
        """Class constructor.  Note that I don't create the forms here – this
        is done later in `from_post_data` and in `from_database`.

        :Parameters:
          - `request`: the current HTTP Request object
          - `deposition_number`: number of the deposition to be edited.  If
            this is ``None``, create a new one.

        :type request: ``HttpRequest``
        :type deposition_number: unicode
        """
        self.user = request.user
        self.user_details = self.user.samples_user_details
        self.deposition = \
            get_object_or_404(institute_models.FiveChamberDeposition, number=deposition_number) if deposition_number else None
        self.deposition_form = self.add_layers_form = self.samples_form = self.remove_from_my_samples_form = None
        self.layer_forms, self.change_layer_forms = [], []
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.json_client = is_json_requested(request)

    def from_post_data(self, post_data):
        """Generate all forms from the post data submitted by the user.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data = post_data
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, institute_models.FiveChamberDeposition, self.post_data)
        if not self.deposition:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(self.post_data)
        self.samples_form = \
            form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.deposition, self.post_data)
        indices = form_utils.collect_subform_indices(self.post_data)
        self.layer_forms = [LayerForm(self.post_data, prefix=str(layer_index)) for layer_index in indices]
        self.change_layer_forms = [ChangeLayerForm(self.post_data, prefix=str(change_layer_index))
                                   for change_layer_index in indices]
        self.edit_description_form = form_utils.EditDescriptionForm(self.post_data) \
            if self.deposition and self.deposition.finished else None

    def from_database(self, query_dict):
        """Create all forms from database data.  This is used if the view was
        retrieved from the user with the HTTP GET method, so there hasn't been
        any post data submitted.

        I have to distinguish all three cases in this method: editing, copying,
        and duplication.

        :Parameters:
          - `query_dict`: dictionary with all given URL query string parameters

        :type query_dict: dict mapping unicode to unicode
        """
        def __read_layer_forms(source_deposition):
            """Generate a set of layer forms from database data.  Note that the
            layers are not returned – instead, they are written directly into
            ``self.layer_forms``.

            :Parameters:
              - `source_deposition`: the deposition from which the layers should be
                taken.  Note that this may be the deposition which is currently
                edited, or the deposition which is duplicated to create a new
                deposition.

            :type source_deposition: `institute_models.FiveChamberDeposition`
            :type destination_deposition_number: unicode
            """
            self.layer_forms = [LayerForm(prefix=str(layer_index), instance=layer,
                                      initial={"number": form_utils.three_digits(layer_index + 1)})
                            for layer_index, layer in enumerate(source_deposition.layers.all())]

        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            source_deposition_query = institute_models.FiveChamberDeposition.objects.filter(number=copy_from)
            if source_deposition_query.count() == 1:
                deposition_data = source_deposition_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["timestamp_inaccuracy"] = 0
                deposition_data["operator"] = self.user.pk
                deposition_data["number"] = utils.get_next_deposition_number("S")
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                __read_layer_forms(source_deposition_query[0])
        if not self.deposition_form:
            if self.deposition:
                # Normal edit of existing deposition
                self.deposition_form = DepositionForm(self.user, instance=self.deposition)
                __read_layer_forms(self.deposition)
            else:
                # New deposition, or duplication has failed
                self.deposition_form = DepositionForm(
                    self.user, initial={"operator": self.user.pk, "timestamp": datetime.datetime.now(),
                                        "number": utils.get_next_deposition_number("S")})
                self.layer_forms, self.change_layer_forms = [], []
        self.samples_form = form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.deposition)
        self.change_layer_forms = [ChangeLayerForm(prefix=str(index)) for index in range(len(self.layer_forms))]
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, institute_models.FiveChamberDeposition)
        self.edit_description_form = form_utils.EditDescriptionForm() \
            if self.deposition and self.deposition.finished else None
        if not self.deposition:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm()

    def __change_structure(self):
        """Apply any layer-based rearrangements the user has requested.  This
        is layer duplication, order changes, appending of layers, and deletion.

        The method has two parts: First, the changes are collected in a data
        structure called ``new_layers``.  Then, I walk through ``new_layers``
        and build a new list ``self.layer_forms`` from it.

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
        `form_utils.normalize_prefixes`), not even across many “post cycles”.
        Only the layer numbers are used for determining the order of layers.

        :Return:
          whether the structure was changed in any way.

        :rtype: bool
        """
        structure_changed = False
        new_layers = [["original", layer_form, change_layer_form]
                      for layer_form, change_layer_form in zip(self.layer_forms, self.change_layer_forms)]

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
        if self.add_layers_form.is_valid():
            for i in range(self.add_layers_form.cleaned_data["number_of_layers_to_add"]):
                new_layers.append(("new", {}))
                structure_changed = True
            # Add MyLayer
            my_layer_data = self.add_layers_form.cleaned_data["my_layer_to_be_added"]
            if my_layer_data is not None:
                new_layers.append(("new", my_layer_data))
                structure_changed = True
            self.add_layers_form = form_utils.AddLayersForm(self.user_details, institute_models.FiveChamberDeposition)

        # Delete layers
        for i in range(len(new_layers) - 1, -1, -1):
            if len(new_layers[i]) == 3:
                change_layer_form = new_layers[i][2]
                if change_layer_form.is_valid() and change_layer_form.cleaned_data["remove_this_layer"]:
                    del new_layers[i]
                    structure_changed = True

        # Apply changes
        next_layer_number = 1
        old_prefixes = [int(layer_form.prefix) for layer_form in self.layer_forms if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.layer_forms = []
        self.change_layer_forms = []
        for new_layer in new_layers:
            if new_layer[0] == "original":
                post_data = self.post_data.copy()
                prefix = new_layer[1].prefix
                post_data[prefix + "-number"] = next_layer_number
                next_layer_number += 1
                self.layer_forms.append(LayerForm(post_data, prefix=prefix))
                self.change_layer_forms.append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = next_layer_number
                    next_layer_number += 1
                    self.layer_forms.append(LayerForm(initial=layer_data, prefix=str(next_prefix)))
                    self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                initial = new_layer[1]
                initial["number"] = next_layer_number
                self.layer_forms.append(LayerForm(initial=initial, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_layer_number += 1
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])
        return structure_changed

    def __is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.
        This function calls the ``is_valid()`` method of all forms, even if one
        of them returns ``False`` (and makes the return value clear
        prematurely).

        :Return:
          whether all forms are valid.

        :rtype: bool
        """
        all_valid = self.deposition_form.is_valid()
        all_valid = (self.add_layers_form.is_valid() or not self.add_layers_form.is_bound) and all_valid
        all_valid = (self.edit_description_form.is_valid() if self.edit_description_form else True) and all_valid
        if not self.deposition:
            all_valid = self.remove_from_my_samples_form.is_valid() and all_valid
        if not self.deposition:
            all_valid = self.samples_form.is_valid() and all_valid
        all_valid = all([layer_form.is_valid() for layer_form in self.layer_forms]) and all_valid
        all_valid = all([(change_layer_form.is_valid() or not change_layer_form.is_bound)
                         for change_layer_form in self.change_layer_forms]) and all_valid
        return all_valid

    def __is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.  For example, no layer number must occur twice, and the
        deposition number must not exist within the database.

        Note that I test many situations here that cannot be achieved with
        using the browser because all number fields are read-only and thus
        inherently referentially valid.  However, the remote client (or a
        manipulated HTTP client) may be used in a malicious way, thus I have to
        test for *all* cases.

        :Return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if not self.layer_forms:
            self.deposition_form.add_error(None, _("No layers given."))
            referentially_valid = False
        if self.deposition_form.is_valid():
            if self.samples_form.is_valid():
                dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                       self.deposition_form.cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(
                        "The sample {samples} is already dead at this time.",
                        "The samples {samples} are already dead at this time.", len(dead_samples)).format(
                        samples=utils.format_enumeration([sample.name for sample in dead_samples]))
                    self.deposition_form.add_error("timestamp", error_message)
                    referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        """Apply all layer changes, check the whole validity of the data, and
        save the forms to the database.  Only the deposition is just updated if
        it already existed.  However, the layers are completely deleted and
        re-constructed from scratch.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `institute_models.FiveChamberDeposition` or ``NoneType``
        """
        database_ready = not self.__change_structure() if not self.json_client else True
        database_ready = self.__is_all_valid() and database_ready
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            deposition = self.deposition_form.save()
            if not self.deposition:
                # Change sample list only for *new* depositions
                deposition.samples = self.samples_form.cleaned_data["sample_list"]
            deposition.layers.all().delete()
            for layer_form in self.layer_forms:
                layer = layer_form.save(commit=False)
                layer.deposition = deposition
                layer.save()
            feed_utils.Reporter(self.user).report_physical_process(
                deposition, self.edit_description_form.cleaned_data if self.edit_description_form else None)
            return deposition

    def get_context_dict(self):
        """Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :Return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"deposition": self.deposition_form, "samples": self.samples_form,
                "layers_and_change_layers": zip(self.layer_forms, self.change_layer_forms),
                "add_layers": self.add_layers_form, "remove_from_my_samples": self.remove_from_my_samples_form,
                "edit_description": self.edit_description_form}


@login_required
def edit(request, deposition_number):
    """Edit or create a 5-chamber deposition.  In case of creation, starting
    with a duplicate of another deposition is also possible if a ``copy-from``
    query string parameter is present (as for the other depositions).

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: number of the deposition to be edited.  If this is
        ``None``, create a new one.

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return form_utils.edit_depositions(request,
                                       deposition_number,
                                       FormSet(request, deposition_number),
                                       institute_models.FiveChamberDeposition,
                                       "samples/edit_five_chamber_deposition.html")

@login_required
def show(request, deposition_number):
    """Show an existing 5-chamber_deposision.  You must be a 5-chamber
    operator *or* be able to view one of the samples affected by this
    deposition in order to be allowed to view it.

    :Parameters:
      - `request`: the current HTTP Request object
      - `deposition_number`: the number (=name) or the deposition

    :type request: ``HttpRequest``
    :type deposition_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    return form_utils.show_depositions(request,
                                       deposition_number,
                                       institute_models.FiveChamberDeposition)
