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


"""
"""

from __future__ import absolute_import, unicode_literals
from chantal_common.utils import append_error, is_json_requested
from chantal_institute import settings
from chantal_institute.mfc_calibrations import get_calibrations_from_datafile
from chantal_institute.views import form_utils
from django import forms
from django.contrib.auth.decorators import login_required
from django.forms.util import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext, \
    ungettext
from samples.views import utils, feed_utils
import chantal_institute.models as ipv_models
import datetime
import re
import decimal
from django.utils.text import capfirst

def calculate_silane_concentration(layer):
    """This method is for calculating the silane concentration. It should be used
    right before the layer is saved into the database.

    :Parameters:
      - `layer`: the uncommitted deposition layer

    :type layer: ``chantal_institute.models_depositions.LADALayer``

    :Returns:
      a tuple of silane concentration at the beginning and at the end of the deposition
      or ``None``.

    :rtype: tuple of floats or tuple of ``None``
    """
    if layer.sih4_1 == layer.sih4_2 == None or layer.h2_1 == layer.h2_2 == None:
        return None, None
    sih4_1 = float(layer.sih4_1 or 0)
    sih4_2 = float(layer.sih4_2 or 0)
    h2_1 = float(layer.h2_1 or 0)
    h2_2 = float(layer.h2_2 or 0)
    sih4_1_end = float(layer.sih4_1_end or 0)
    sih4_2_end = float(layer.sih4_2_end or 0)
    h2_1_end = float(layer.h2_1_end or 0)
    h2_2_end = float(layer.h2_2_end or 0)
    calibrations = get_calibrations_from_datafile(settings.LADA_MFC_CALIBRATION_FILE_PATH, "lada")
    calibrations.sort(reverse=True)
    for calibration in calibrations:
        if layer.date > calibration.date:
            calibration_set = calibration
            break
    silane = (calibration_set.get_real_flow(sih4_1, "sih4_{0}".format(layer.get_sih4_mfc_number_1_display() or "1.1")) +
              calibration_set.get_real_flow(sih4_2, "sih4_{0}".format(layer.get_sih4_mfc_number_2_display() or "1.1"))) * 0.6
    hydrogen = calibration_set.get_real_flow(h2_1, "h2_{0}".format(layer.get_h2_mfc_number_1_display() or "1.1")) + \
               calibration_set.get_real_flow(h2_2, "h2_{0}".format(layer.get_h2_mfc_number_2_display() or "1.1"))
    silane_end = (calibration_set.get_real_flow(sih4_1_end, "sih4_{0}".format(layer.get_sih4_mfc_number_1_display() or "1.1")) +
                  calibration_set.get_real_flow(sih4_2_end, "sih4_{0}".format(layer.get_sih4_mfc_number_2_display() or "1.1"))) * 0.6 \
                  if not layer.sih4_1_end == layer.sih4_2_end == None else silane
    hydrogen_end = calibration_set.get_real_flow(h2_1_end, "h2_{0}".format(layer.get_h2_mfc_number_1_display() or "1.1")) + \
                   calibration_set.get_real_flow(h2_2_end, "h2_{0}".format(layer.get_h2_mfc_number_2_display() or "1.1")) \
                   if not layer.h2_1_end == layer.h2_2_end == None else hydrogen
    # Cheap way to cut the digits
    calculate_sc = lambda s, h: decimal.Decimal("{0:5.2f}".format(100 * s / (s + h))) if s + h != 0 else None
    sc = calculate_sc(silane, hydrogen)
    sc_end = calculate_sc(silane_end, hydrogen_end)
    if sc == sc_end:
        sc_end = None
    return sc, sc_end

class DepositionForm(form_utils.ProcessForm):
    """Model form for the deposition main data.  I only overwrite ``operator``
    in order to have full real names.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_("Operator"))
    customer = form_utils.UserField(label=capfirst(_("customer")))

    def __init__(self, user, data=None, **kwargs):
        """Class constructor just for changing the appearance of the number
        field."""
        super(DepositionForm, self).__init__(data, **kwargs)
        self.fields["number"].widget.attrs.update({"style": "font-size: large", "size": "8"})
        deposition = kwargs.get("instance")
        self.fields["operator"].set_operator(deposition.operator if deposition else user, user.is_staff)
        self.fields["operator"].initial = deposition.operator.pk if deposition else user.pk
        self.already_finished = deposition and deposition.finished
        self.previous_deposition_number = deposition.number if deposition else None
        self.fields["customer"].set_users(user)
        if self.already_finished:
            self.fields["number"].widget.attrs.update({"readonly": "readonly"})

    def clean_number(self):
        number = self.cleaned_data["number"]
        if self.already_finished and (self.previous_deposition_number and self.previous_deposition_number != number):
            raise ValidationError(_("The deposition number must not be changed."))
        return form_utils.clean_deposition_number_field(number, "D")

    def validate_unique(self):
        """Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `FormSet.__is_referentially_valid`.  I cannot use
        Django's built-in test anyway because it leads to an error message in
        wrong German (difficult to fix, even for the Django guys).
        """
        pass

    def clean(self):
        if "number" in self.cleaned_data and "timestamp" in self.cleaned_data:
            if not re.match(self.cleaned_data["timestamp"].strftime("%y"), self.cleaned_data["number"][:2]):
                append_error(self, _("The first two digits must match the year of the deposition."), "number")
                del self.cleaned_data["number"]
        return self.cleaned_data

    class Meta:
        model = ipv_models.LADADeposition
        exclude = ("external_operator",)


class LayerForm(forms.ModelForm):
    """Model form for a single layer.
    """
    _ = ugettext_lazy

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
        for fieldname in ["date", "ch4", "co2", "pressure", "base_pressure", "electrodes_distance", "temperature_substrate",
                          "temperature_heater", "temperature_heater_depo", "additional_gas_flow",
                          "tmb_1", "tmb_2", "v_lq", "pendulum_lq", "layer_type"]:
            self.fields[fieldname].widget.attrs["size"] = "10"
        for fieldname in ["sih4_1", "sih4_1_end", "sih4_2", "sih4_2_end", "h2_1", "h2_1_end", "h2_2", "h2_2_end",
                          "ph3_1", "ph3_2", "ph3_1_end", "ph3_2_end", "power_1", "power_2", "power_reflected_1",
                          "power_reflected_2", "time_1", "time_2", "cl_1", "cl_2", "ct_1", "ct_2", "u_dc_1", "u_dc_2"]:
            self.fields[fieldname].widget.attrs["size"] = "5"
        self.fields["comments"].widget.attrs["cols"] = "40"


    def clean(self):
        def check_gradient(fieldname, gasname):
            fieldname_end = "{0}_end".format(fieldname)
            if self.cleaned_data.get(fieldname) is not None and \
                    self.cleaned_data.get(fieldname_end) is not None \
                    and self.cleaned_data[fieldname_end] == self.cleaned_data[fieldname]:
                append_error(self,
                    _("If given, this field must be different from the initial {gasname} flow.").format(gasname=gasname),
                    fieldname_end)
                del self.cleaned_data[fieldname_end]

        def check_mfc(fieldname, gasname):
            fieldname_end = "{0}_end".format(fieldname)
            mfc_fieldname = "{0}_mfc_number_{1}".format(fieldname[:-2], fieldname[-1])
            if (self.cleaned_data.get(fieldname) or self.cleaned_data.get(fieldname_end)) \
                    and not self.cleaned_data.get(mfc_fieldname):
                append_error(self,
                        _("You have to select the number of the MFC."), mfc_fieldname)
            elif self.cleaned_data.get(mfc_fieldname) \
                    and not (self.cleaned_data.get(fieldname) or self.cleaned_data.get(fieldname_end)):
                append_error(self,
                        _("No {gasname} flow rate is given.").format(gasname=gasname), mfc_fieldname)
                del self.cleaned_data[mfc_fieldname]

        check_gradient("sih4_1", "SiH₄")
        check_gradient("sih4_2", "SiH₄")
        check_gradient("h2_1", "H₂")
        check_gradient("h2_2", "H₂")
        check_gradient("ph3_1", "PH₃")
        check_gradient("ph3_2", "PH₃")
        check_mfc("sih4_1", "SiH₄")
        check_mfc("sih4_2", "SiH₄")
        check_mfc("h2_1", "H₂")
        check_mfc("h2_2", "H₂")
        if self.cleaned_data.get("additional_gas") and not self.cleaned_data.get("additional_gas_flow"):
            append_error(self, _("If you select {gasname}, you have to specifiy the gas flow rate.") \
                        .format(gasname=self.cleaned_data.get("additional_gas")),
                        "additional_gas_flow")
        elif self.cleaned_data.get("additional_gas_flow") and not self.cleaned_data.get("additional_gas"):
            append_error(self, _("Please select a gas for the gas flow rate."), "additional_gas")
        if self.cleaned_data.get("time_1") is None \
                and not (self.cleaned_data.get("v_lq") and self.cleaned_data.get("pendulum_lq")):
            append_error(self, _("This field is required."), "time_1")
            del self.cleaned_data["time_1"]
        return self.cleaned_data

    class Meta:
        model = ipv_models.LADALayer
        exclude = ("deposition", "silane_concentration", "silane_concentration_end")


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
    """Class for holding all forms of the lada deposition views, and for
    all methods working on these forms.

    :ivar deposition: the deposition to be edited.  If it is ``None``, we
      create a new one.  This is very important because testing ``deposition``
      is the only way to distinguish between editing or creating.

    :type deposition: `ipv_models.LADADeposition` or ``NoneType``
    """
    deposition_number_pattern = re.compile(r"(?P<prefix>\d\dD-)(?P<number>\d{3,4})$")

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
            get_object_or_404(ipv_models.LADADeposition, number=deposition_number) if deposition_number else None
        self.deposition_form = self.add_layers_form = self.samples_form = self.remove_from_my_samples_form = None
        self.layer_forms, self.change_layer_forms = [], []
        self.preset_sample = utils.extract_preset_sample(request) if not self.deposition else None
        self.post_data = None
        self.edit_description_form = None
        self.json_client = is_json_requested(request)

    def from_post_data(self, post_data):
        """Generate all forms from the post data submitted by the user.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data = post_data
        self.deposition_form = DepositionForm(self.user, self.post_data, instance=self.deposition)
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, ipv_models.LADADeposition, self.post_data)
        if not self.deposition:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(self.post_data)
        self.samples_form = \
            form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.deposition, self.post_data)
        indices = form_utils.collect_subform_indices(self.post_data)
        self.layer_forms = [LayerForm(self.post_data, prefix=str(layer_index)) for layer_index in indices]
        self.change_layer_forms = [ChangeLayerForm(self.post_data, prefix=str(change_layer_index))
                                   for change_layer_index in indices]
        self.edit_description_form = form_utils.EditDescriptionForm(self.post_data) if self.deposition else None

    def __get_next_deposition_number(self):
        """Normally i would use the ``get_next_deposition`` method from utils.py, but
        for the lada-deposition i have to use the layer numbers to determinate the
        next deposition number.

        :Return:
          A so-far unused deposition number for the current calendar year for the
          given deposition apparatus.
        """
        prefix = r"{0}{1}-".format(datetime.date.today().strftime("%y"), "D")
        pattern_string = r"^{0}\d+".format(re.escape(prefix))
        deposition_numbers = \
            ipv_models.LADADeposition.objects.select_related('layers__number', 'number') \
                .filter(number__regex=pattern_string).values_list("layers__number", flat=True)
        next_number = max(deposition_numbers) + 1 if deposition_numbers else 1
        return prefix + "{0:04}".format(next_number)


    def __read_layer_forms(self, source_deposition, destination_deposition_number=None):
        """Generate a set of layer forms from database data.  Note that the
        layers are not returned – instead, they are written directly into
        ``self.layer_forms``.

        :Parameters:
          - `source_deposition`: the deposition from which the layers should be
            taken.  Note that this may be the deposition which is currently
            edited, or the deposition which is duplicated to create a new
            deposition.
          - `destination_deposition_number`: if given, duplicate into a
            deposition with this number.  If none, ``source_deposition``
            already contains the proper deposition number.

        :type source_deposition: `ipv_models.LADADeposition`
        :type destination_deposition_number: unicode
        """
        layers = source_deposition.layers
        if destination_deposition_number:
            base_number = int(self.deposition_number_pattern.match(destination_deposition_number).group("number"))
            layer_dates = layers.count() * [datetime.date.today()]
        else:
            base_number = int(self.deposition_number_pattern.match(source_deposition.number).group("number"))
            layer_dates = [layer.date for layer in source_deposition.layers.all()]
        self.layer_forms = [LayerForm(prefix=str(layer_index), instance=layer,
                                      initial={"number": "{0:04}".format(base_number + layer_index),
                                               "date": layer_dates[layer_index]})
                            for layer_index, layer in enumerate(layers.all())]

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
        copy_from = query_dict.get("copy_from")
        if not self.deposition and copy_from:
            # Duplication of a deposition
            source_deposition_query = ipv_models.LADADeposition.objects.filter(number=copy_from)
            if source_deposition_query.exists():
                deposition_data = source_deposition_query.values()[0]
                deposition_data["timestamp"] = datetime.datetime.now()
                deposition_data["timestamp_inaccuracy"] = 0
                deposition_data["operator"] = self.user.pk
                prefix, number = self.__get_next_deposition_number().split("-")
                deposition_data["number"] = "{0}-{1:04}".format(prefix, int(number))
                self.deposition_form = DepositionForm(self.user, initial=deposition_data)
                self.__read_layer_forms(source_deposition_query[0], deposition_data["number"])
        if not self.deposition_form:
            if self.deposition:
                # Normal edit of existing deposition
                self.deposition_form = DepositionForm(self.user, instance=self.deposition)
                self.__read_layer_forms(self.deposition)
            else:
                # New deposition, or duplication has failed
                prefix, number = self.__get_next_deposition_number().split("-")
                self.deposition_form = DepositionForm(
                    self.user, initial={"operator": self.user.pk, "timestamp": datetime.datetime.now(),
                                        "number": "{0}-{1:04}".format(prefix, int(number))})
                self.layer_forms, self.change_layer_forms = [], []
        self.samples_form = form_utils.DepositionSamplesForm(self.user, self.preset_sample, self.deposition)
        self.change_layer_forms = [ChangeLayerForm(prefix=str(index)) for index in range(len(self.layer_forms))]
        self.add_layers_form = form_utils.AddLayersForm(self.user_details, ipv_models.LADADeposition)
        if not self.deposition:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm()
        self.edit_description_form = form_utils.EditDescriptionForm() if self.deposition else None

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
            self.add_layers_form = form_utils.AddLayersForm(self.user_details, ipv_models.LADADeposition)

        # Delete layers
        for i in range(len(new_layers) - 1, -1, -1):
            if len(new_layers[i]) == 3:
                change_layer_form = new_layers[i][2]
                if change_layer_form.is_valid() and change_layer_form.cleaned_data["remove_this_layer"]:
                    del new_layers[i]
                    structure_changed = True

        # Apply changes
        next_full_number = None
        if self.deposition:
            next_full_number = "{0}{1:04}".format(self.deposition.number[:4], self.deposition.layers.all()[0].number)
        elif self.deposition_form.is_valid():
            match = self.deposition_number_pattern.match(self.deposition_form.cleaned_data["number"])
            if match:
                number_of_first_layer = int(match.group("number"))
                next_full_number = "{0}{1:04}".format(match.group("prefix"), number_of_first_layer)
        if not next_full_number:
            prefix, number = self.__get_next_deposition_number().split("-")
            next_full_number = "{0}-{1:04}".format(prefix, int(number))
        deposition_number_match = self.deposition_number_pattern.match(next_full_number)
        next_layer_number = int(deposition_number_match.group("number"))
        old_prefixes = [int(layer_form.prefix) for layer_form in self.layer_forms if layer_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.layer_forms = []
        self.change_layer_forms = []
        for new_layer in new_layers:
            if new_layer[0] == "original":
                post_data = self.post_data.copy()
                prefix = new_layer[1].prefix
                post_data[prefix + "-number"] = "{0:04}".format(next_layer_number)
                next_layer_number += 1
                self.layer_forms.append(LayerForm(post_data, prefix=prefix))
                self.change_layer_forms.append(new_layer[2])
            elif new_layer[0] == "duplicate":
                original_layer = new_layer[1]
                if original_layer.is_valid():
                    layer_data = original_layer.cleaned_data
                    layer_data["number"] = "{0:04}".format(next_layer_number)
                    next_layer_number += 1
                    self.layer_forms.append(LayerForm(initial=layer_data, prefix=str(next_prefix)))
                    self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                    next_prefix += 1
            elif new_layer[0] == "new":
                initial = new_layer[1]
                initial["number"] = "{0:04}".format(next_layer_number)
                self.layer_forms.append(LayerForm(initial=initial, prefix=str(next_prefix)))
                self.change_layer_forms.append(ChangeLayerForm(prefix=str(next_prefix)))
                next_layer_number += 1
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_layers structure: " + new_layer[0])
        # Finally, adjust the deposition number to the new number of layers.
        post_data = self.post_data.copy()
        post_data["number"] = deposition_number_match.group("prefix") + \
            "{0:04}".format(next_layer_number - len(self.layer_forms) if self.layer_forms else next_layer_number)
        self.deposition_form = DepositionForm(self.user, post_data, instance=self.deposition)

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
        if not self.deposition:
            all_valid = self.remove_from_my_samples_form.is_valid() and all_valid
        if not self.deposition:
            all_valid = self.samples_form.is_valid() and all_valid
        all_valid = (self.edit_description_form.is_valid() if self.edit_description_form else True) and all_valid
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
            append_error(self.deposition_form, _("No layers given."))
            referentially_valid = False
        if self.deposition_form.is_valid():
            deposition_number = self.deposition_form.cleaned_data["number"]
            match = self.deposition_number_pattern.match(deposition_number)
            deposition_prefix = match.group("prefix")
            number_only = int(match.group("number"))
            #max_layer_number = int(self.__get_next_deposition_number()[len(deposition_prefix):]) - 1
            if self.deposition:
                if self.layer_forms and self.layer_forms[0].is_valid() and \
                        self.layer_forms[0].cleaned_data["number"] != self.deposition.layers.all()[0].number:
                    append_error(self.deposition_form, _("You can't change the number of the first layer."))
                    referentially_valid = False
                pattern_string = r"^{0}\d+".format(re.escape(deposition_prefix))
                higher_deposition_numbers = ipv_models.LADADeposition.objects.filter(number__regex=pattern_string) \
                    .values_list("number", flat=True).iterator()
                higher_deposition_numbers = [int(higher_deposition_number[len(deposition_prefix):len(deposition_prefix) + 4])
                                             for higher_deposition_number in higher_deposition_numbers
                                             if higher_deposition_number > deposition_number]
                if higher_deposition_numbers:
                    if number_only + len(self.layer_forms) > min(higher_deposition_numbers):
                        append_error(self.deposition_form, _("New layers collide with following deposition."))
                        referentially_valid = False
            elif self.layer_forms and self.layer_forms[0].is_valid():
                start_date = datetime.date(self.layer_forms[0].cleaned_data["date"].year, 1, 1)
                end_date = self.layer_forms[0].cleaned_data["date"]
                if ipv_models.LADALayer.objects.filter(number=self.layer_forms[0].cleaned_data["number"],
                                                            date__range=(start_date, end_date)).exists():
                        #self.layer_forms[0].cleaned_data["number"] <= max_layer_number:
                    append_error(self.deposition_form, _("Overlap with previous deposition numbers."))
                    referentially_valid = False
            if self.samples_form.is_valid():
                dead_samples = form_utils.dead_samples(self.samples_form.cleaned_data["sample_list"],
                                                       self.deposition_form.cleaned_data["timestamp"])
                if dead_samples:
                    error_message = ungettext(
                        "The sample {samples} is already dead at this time.",
                        "The samples {samples} are already dead at this time.", len(dead_samples)).format(
                        samples=utils.format_enumeration([sample.name for sample in dead_samples]))
                    append_error(self.deposition_form, error_message, "timestamp")
                    referentially_valid = False
            for i, layer_form in enumerate(self.layer_forms):
                if layer_form.is_valid():
                    if layer_form.cleaned_data["number"] - i != number_only:
                        append_error(layer_form, _("Layer number is not consecutive."))
                        referentially_valid = False
                    if layer_form.cleaned_data["date"] > self.deposition_form.cleaned_data["timestamp"].date():
                        append_error(layer_form, _("Layer date must not be after deposition timestamp."))
                        referentially_valid = False
                    if i > 0 and self.layer_forms[i - 1].is_valid() \
                          and layer_form.cleaned_data["date"] < self.layer_forms[i - 1].cleaned_data["date"]:
                        append_error(layer_form, _("Layer date is not consecutive."))
                        referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        """Apply all layer changes, check the whole validity of the data, and
        save the forms to the database.  Only the deposition is just updated if
        it already existed.  However, the layers are completely deleted and
        re-constructed from scratch.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `ipv_models.LADADeposition` or ``NoneType``
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
                layer.silane_concentration, layer.silane_concentration_end = calculate_silane_concentration(layer)
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
    """Edit or create a lada deposition.  In case of creation, starting
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
    return form_utils.edit_depositions(request, deposition_number, FormSet(request, deposition_number),
                                       ipv_models.LADADeposition, "samples/edit_lada_deposition.html")


@login_required
def show(request, deposition_number):
    """Show an existing lada_deposision.  You must be a lada
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
    return form_utils.show_depositions(request, deposition_number, ipv_models.LADADeposition)
