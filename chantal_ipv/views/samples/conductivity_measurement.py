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

import datetime, re, codecs, os, decimal
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django.db.models import Q
import django.contrib.auth.models
from chantal_common.utils import append_error, is_json_requested, check_filepath
from samples.views import utils, feed_utils
from samples.views.shared_utils import read_techplot_file, PlotError
from chantal_ipv.views import form_utils
from samples import permissions
import chantal_ipv.models as ipv_models


class ConductivityMeasurementsForm(form_utils.ProcessForm):
    """
    """
    _ = ugettext_lazy
    combined_operator = form_utils.OperatorField(label=_("Operator"))

    def __init__(self, user, *args, **kwargs):
        """Form constructor.
        """
        super(ConductivityMeasurementsForm, self).__init__(*args, **kwargs)
        old_instance = kwargs.get("instance")
        self.user = user
        self.fields["combined_operator"].set_choices(user, old_instance)
        if not user.is_staff:
            self.fields["external_operator"].choices = []
            self.fields["operator"].choices = []
            self.fields["operator"].required = False
        else:
            self.fields["combined_operator"].required = False

    def clean(self):
        cleaned_data = self.cleaned_data
        final_operator = cleaned_data.get("operator")
        final_external_operator = cleaned_data.get("external_operator")
        if cleaned_data.get("combined_operator"):
            operator, external_operator = cleaned_data["combined_operator"]
            if operator:
                if final_operator and final_operator != operator:
                    append_error(self, "Your operator and combined operator didn't match.", "combined_operator")
                else:
                    final_operator = operator
            if external_operator:
                if final_external_operator and final_external_operator != external_operator:
                    append_error(self, "Your external operator and combined external operator didn't match.",
                                 "combined_external_operator")
                else:
                    final_external_operator = external_operator
        if not final_operator:
            # Can only happen for non-staff.  I deliberately overwrite a
            # previous operator because this way, we can log who changed it.
            final_operator = self.user
        cleaned_data["operator"], cleaned_data["external_operator"] = final_operator, final_external_operator
        return cleaned_data

    class Meta:
        model = ipv_models.ConductivityMeasurementSet
        exclude = ("timestamp", "timestamp_inaccuracy")


class SingleConductivityMeasurementForm(forms.ModelForm):
    """Model form for the core Conductivity measurement data.
    """

    lf_knl_number_pattern = re.compile(r"[a-z]{2,3}\d+$")

    def __init__(self, *args, **kwargs):
        """Form constructor.  I just adjust layout here.
        """
        self.set_pk = kwargs.get("set_pk")
        if "set_pk" in kwargs:
            del kwargs["set_pk"]
        super(SingleConductivityMeasurementForm, self).__init__(*args, **kwargs)
        self.fields["number"].widget.attrs["size"] = "10"
        self.fields["filepath"].widget.attrs["size"] = "60"
        self.fields["tempering_time"].widget.attrs["size"] = self.fields["tempering_temperature"].widget.attrs["size"] = "10"

    def clean_filepath(self):
        _ = ugettext
        filepath = check_filepath(self.cleaned_data["filepath"], settings.MEASUREMENT_DATA_ROOT_DIR)
        self.file_content = {}
        self.file_content["kind"] = "characteristic curve" if "knl" in filepath else "sigma"
        if self.file_content["kind"] == "sigma":
            full_filepath = os.path.join(settings.MEASUREMENT_DATA_ROOT_DIR, filepath)
            try:
                temperatures, sigmas, voltages = read_techplot_file(full_filepath, (0, 2, 3))
            except PlotError:
                raise ValidationError(_("The file is not a valid datafile."))
            if not temperatures or not sigmas or not voltages:
                raise ValidationError(_("The file is not a valid datafile."))
            for line in codecs.open(full_filepath, encoding="cp1252"):
                if line.startswith("Probendicke/nm:"):
                    try:
                        assumed_thickness = decimal.Decimal(line.partition(":")[2].rstrip())
                        if 0 <= assumed_thickness < 10000000:
                            self.file_content["assumed_thickness"] = assumed_thickness
                    except (ValueError, decimal.InvalidOperation):
                        pass
            self.file_content["kind"] = "single sigma" if len(temperatures) == 1 else "temperature-dependent"
            if self.file_content["kind"] == "single sigma":
                temperature = str(temperatures[0])
                if temperature != "999.9":
                    self.file_content["temperature"] = decimal.Decimal(temperature)
                self.file_content["sigma"] = sigmas[0]
                voltage = decimal.Decimal(str(voltages[0]))
                if voltage != decimal.Decimal("Infinity"):
                    self.file_content["voltage"] = voltage
        return filepath

    def validate_unique(self):
        pass

    def clean_timestamp(self):
        """Forbid timestamps that are in the future.
        """
        timestamp = self.cleaned_data["timestamp"]
        if timestamp > datetime.datetime.now():
            raise ValidationError(_("The timestamp must not be in the future."))
        return timestamp

    def save(self, commit=True):
        instance = super(SingleConductivityMeasurementForm, self).save(commit=False)
        instance.kind = self.file_content["kind"]
        instance.sigma = self.file_content.get("sigma")
        instance.voltage = self.file_content.get("voltage")
        instance.assumed_thickness = self.file_content.get("assumed_thickness")
        instance.temperature = self.file_content.get("temperature")
        if commit:
            instance.save()
        return instance

    class Meta:
        model = ipv_models.SingleConductivityMeasurement
        exclude = ("measurement_set", "sigma", "voltage", "assumed_thickness", "temperature", "kind")


class AddMeasurementForm(forms.Form):
    _ = ugettext_lazy
    number_of_measurements_to_add = forms.IntegerField(label=_("Number of measurements to be added"),
                                                       min_value=0, max_value=10, required=False)

    def __init__(self, data=None, **kwargs):
        super(AddMeasurementForm, self).__init__(data, **kwargs)

    def clean_number_of_measurements_to_add(self):
        return utils.int_or_zero(self.cleaned_data["number_of_measurements_to_add"])


class RemoveMeasurementForm(forms.Form):
    _ = ugettext_lazy
    remove_measurement = forms.BooleanField(label=_("Remove Measurement"), required=False)

    def __init__(self, data=None, **kwargs):
        super(RemoveMeasurementForm, self).__init__(data, **kwargs)


class FormSet(object):

    def __init__(self, request, conductivity_measurements_pk):
        self.user = request.user
        self.user_details = self.user.samples_user_details
        self.conductivity_measurements_pk = conductivity_measurements_pk
        self.conductivity_measurements = \
            get_object_or_404(ipv_models.ConductivityMeasurementSet, pk=conductivity_measurements_pk) \
            if conductivity_measurements_pk else None
        self.conductivity_measurements_form = self.add_measurement_form = self.samples_form = \
            self.remove_from_my_samples_form = self.edit_description_form = None
        self.measurement_forms, self.remove_measurement_forms = [], []
        self.preset_sample = utils.extract_preset_sample(request) if not self.conductivity_measurements else None
        self.post_data = None
        self.json_client = is_json_requested(request)

    def from_post_data(self, post_data):
        """Generate all forms from the post data submitted by the user.

        :Parameters:
          - `post_data`: the result from ``request.POST``

        :type post_data: ``QueryDict``
        """
        self.post_data = post_data
        self.edit_description_form = form_utils.EditDescriptionForm(post_data) if self.conductivity_measurements else None
        self.conductivity_measurements_form = \
            ConductivityMeasurementsForm(self.user, self.post_data, instance=self.conductivity_measurements)
        self.samples_form = form_utils.SampleForm(self.user, self.conductivity_measurements, self.preset_sample, self.post_data)
        indices = form_utils.collect_subform_indices(self.post_data)
        self.measurement_forms = [SingleConductivityMeasurementForm(self.post_data, prefix=str(measurement_index),
                                                                   set_pk=self.conductivity_measurements.pk \
                                                                   if self.conductivity_measurements else None) \
                               for measurement_index in indices]
        self.add_measurement_form = AddMeasurementForm(self.post_data)
        self.remove_measurement_forms = [RemoveMeasurementForm(self.post_data, prefix=str(remove_measurement_index))
                               for remove_measurement_index in indices]
        if not self.conductivity_measurements:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm(self.post_data)

    def from_database(self, query_dict):
        if not self.conductivity_measurements_form:
            if self.conductivity_measurements:
                self.conductivity_measurements_form = \
                    ConductivityMeasurementsForm(self.user, instance=self.conductivity_measurements)
                self.measurement_forms = [
                    SingleConductivityMeasurementForm(prefix=str(index), instance=single_measurement,
                                                      initial={"number": form_utils.three_digits(index + 1)},
                                                      set_pk=self.conductivity_measurements.pk)
                    for index, single_measurement in enumerate(self.conductivity_measurements.single_measurements.all())]
            else:
                self.conductivity_measurements_form = ConductivityMeasurementsForm(self.user,
                                        initial={"operator": self.user.pk, "timestamp": datetime.datetime.now()})
                self.measurement_forms, self.remove_measurement_forms = [], []
        self.add_measurement_form = AddMeasurementForm()
        self.edit_description_form = form_utils.EditDescriptionForm() if self.conductivity_measurements else None
        self.samples_form = form_utils.SampleForm(self.user, self.conductivity_measurements, self.preset_sample)
        self.remove_measurement_forms = [RemoveMeasurementForm(prefix=str(index))
                                         for index in range(len(self.measurement_forms))]
        if not self.conductivity_measurements:
            self.remove_from_my_samples_form = form_utils.RemoveFromMySamplesForm()


    def __change_structure(self):
        structure_changed = False
        new_measurments = [["original", measurement_form, remove_measurement_form]
                           for measurement_form, remove_measurement_form in
                           zip(self.measurement_forms, self.remove_measurement_forms)]

        # Add measurements
        if self.add_measurement_form.is_valid():
            for i in range(self.add_measurement_form.cleaned_data["number_of_measurements_to_add"]):
                new_measurments.append(("new", {}))
                structure_changed = True
            self.add_measurement_form = AddMeasurementForm()

        # Delete measurements
        for i in range(len(new_measurments) - 1, -1, -1):
            if len(new_measurments[i]) == 3:
                remove_measurement_form = new_measurments[i][2]
                if remove_measurement_form.is_valid() and remove_measurement_form.cleaned_data["remove_measurement"]:
                    del new_measurments[i]
                    structure_changed = True

        next_measurement_number = 1
        old_prefixes = [int(measurement_form.prefix) for measurement_form in self.measurement_forms
                        if measurement_form.is_bound]
        next_prefix = max(old_prefixes) + 1 if old_prefixes else 0
        self.measurement_forms = []
        self.remove_measurement_forms = []
        for new_measurment in new_measurments:
            if new_measurment[0] == "original":
                post_data = self.post_data.copy()
                prefix = new_measurment[1].prefix
                post_data[prefix + "-number"] = next_measurement_number
                next_measurement_number += 1
                self.measurement_forms.append(SingleConductivityMeasurementForm(post_data, prefix=prefix, \
                                                                set_pk=self.conductivity_measurements.pk \
                                                                   if self.conductivity_measurements else None))
                self.remove_measurement_forms.append(new_measurment[2])
            elif new_measurment[0] == "new":
                initial = new_measurment[1]
                initial["number"] = next_measurement_number
                initial["timestamp"] = datetime.datetime.now()
                self.measurement_forms.append(SingleConductivityMeasurementForm(initial=initial, prefix=str(next_prefix)))
                self.remove_measurement_forms.append(RemoveMeasurementForm(prefix=str(next_prefix)))
                next_measurement_number += 1
                next_prefix += 1
            else:
                raise AssertionError("Wrong first field in new_measurments structure: " + new_measurment[0])
        return structure_changed


    def __is_all_valid(self):
        """Tests the “inner” validity of all forms belonging to this view.  This
        function calls the ``is_valid()`` method of all forms, even if one of them
        returns ``False`` (and makes the return value clear prematurely).

        :Return:
          whether all forms are valid, i.e. their ``is_valid`` method returns
          ``True``.

        :rtype: bool
        """
        all_valid = self.conductivity_measurements_form.is_valid()
        all_valid = (self.add_measurement_form.is_valid() or not self.add_measurement_form.is_bound) and all_valid
        all_valid = all([measurement_form.is_valid() for measurement_form in self.measurement_forms]) and all_valid
        all_valid = all([(remove_measurement_form.is_valid() or not remove_measurement_form.is_bound)\
                     for remove_measurement_form in self.remove_measurement_forms]) and all_valid
        all_valid = self.samples_form.is_valid() and all_valid
        if self.remove_from_my_samples_form:
            all_valid = self.remove_from_my_samples_form.is_valid() and all_valid
        if self.edit_description_form:
            all_valid = self.edit_description_form.is_valid() and all_valid
        return all_valid


    def __is_referentially_valid(self):
        """Test whether the forms are consistent with each other and with the
        database.  In particular, it tests whether the sample is still “alive” at
        the time of the measurement and whether the related data file exists.

        :Return:
          whether the forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if not self.measurement_forms:
            append_error(self.samples_form, _("No measurenents given."))
            referentially_valid = False
        if self.conductivity_measurements_form and self.conductivity_measurements_form.is_valid():
            if self.samples_form.is_valid() and referentially_valid:
                sample = self.samples_form.cleaned_data["sample"]
                timestamp = self.conductivity_measurements_form.cleaned_data.get("timestamp")
                if timestamp and form_utils.dead_samples([sample], timestamp):
                    append_error(self.conductivity_measurements_form, _("Sample is already dead at this time."),
                                 "timestamp")
                    referentially_valid = False
            for measurement_form in self.measurement_forms:
                if measurement_form.is_valid():
                    filepath = measurement_form.cleaned_data["filepath"]
                    query_set = ipv_models.SingleConductivityMeasurement.objects.filter(filepath=filepath)
                    if self.conductivity_measurements_pk:
                        query_set = query_set.exclude(measurement_set__id=self.conductivity_measurements_pk)
                    if query_set.exists():
                        append_error(measurement_form, _("The file already exists."), "filepath")
                        referentially_valid = False
        else:
            referentially_valid = False
        return referentially_valid

    def save_to_database(self):
        """Apply all measurement changes, check the whole validity of the data, and
        save the forms to the database.  Only the measurement set is just updated if
        it already existed.  However, the single measurements are completely deleted and
        re-constructed from scratch.

        :Return:
          The saved deposition object, or ``None`` if validation failed

        :rtype: `ipv_models.ConductivityMeasurementSet` or ``NoneType``
        """
        database_ready = not self.__change_structure() if not self.json_client else True
        database_ready = self.__is_all_valid() and database_ready
        database_ready = self.__is_referentially_valid() and database_ready
        if database_ready:
            conductivity_measurements = self.conductivity_measurements_form.save(commit=False)
            conductivity_measurements.timestamp, conductivity_measurements.timestamp_inaccuracy = \
                sorted([(measurement_form.cleaned_data["timestamp"], measurement_form.cleaned_data["timestamp_inaccuracy"])
                        for measurement_form in self.measurement_forms], reverse=True)[0]
            conductivity_measurements.save()
            conductivity_measurements.samples = [self.samples_form.cleaned_data["sample"]]
            conductivity_measurements.single_measurements.all().delete()
            for measurement_form in self.measurement_forms:
                measurement = measurement_form.save(commit=False)
                measurement.measurement_set = conductivity_measurements
                measurement.save()
            return conductivity_measurements


@login_required
def edit(request, conductivity_set_pk):
    """Edit and create view for conductivity measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `conductivity_set_pk`: The conductivity number of the conductivity process
        to be edited.  If it is ``None``, a new measurement is added to the
        database.

    :type request: ``HttpRequest``
    :type process_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    form_set = FormSet(request, conductivity_set_pk)
    permissions.assert_can_add_edit_physical_process(request.user, form_set.conductivity_measurements,
                                                     ipv_models.ConductivityMeasurementSet)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        conductivity_measurements = form_set.save_to_database()
        if conductivity_measurements:
            reporter = request.user if not request.user.is_staff \
                else form_set.conductivity_measurements_form.cleaned_data["operator"]
            feed_utils.Reporter(reporter).report_physical_process(
                conductivity_measurements,
                form_set.edit_description_form.cleaned_data if form_set.edit_description_form else None)
            if form_set.remove_from_my_samples_form and \
                    form_set.remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples([form_set.samples_form.cleaned_data["sample"]], request.user)
            success_report = \
                _("{process} was successfully changed in the database.").format(process=conductivity_measurements) \
                if conductivity_set_pk else \
                _("{process} was successfully added to the database.").format(process=conductivity_measurements)
            return utils.successful_response(request, success_report, json_response=conductivity_measurements.pk)
    else:
        form_set.from_database(utils.parse_query_string(request))
    title = _("Conductivity measurements of {sample}").format(sample=form_set.conductivity_measurements.samples.get()) \
        if conductivity_set_pk else _("Add conductivity measurements")
    return render_to_response("samples/edit_conductivity_measurement.html",
                              {"title": title,
                               "conductivity_measurement": form_set.conductivity_measurements_form,
                               "conductivity_measurements": zip(form_set.measurement_forms,
                                                                form_set.remove_measurement_forms),
                               "sample": form_set.samples_form,
                               "add_measurement": form_set.add_measurement_form,
                               "remove_from_my_samples": form_set.remove_from_my_samples_form,
                               "edit_description": form_set.edit_description_form},
                              context_instance=RequestContext(request))
