#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""All the views for the PDS measurements.  This is significantly simpler than
the views for deposition systems (mostly because the rearrangement of layers
doesn't happen here).
"""

import datetime, os.path, re, codecs
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms.util import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
import django.contrib.auth.models
from chantal.samples.views import utils, form_utils
from chantal.samples import models, permissions
from chantal import settings

root_dir = "/home/bronger/temp/pds/" if settings.IS_TESTSERVER else "/windows/T_www-data/daten/pds/"
raw_filename_pattern = re.compile(r"(?P<prefix>.*)pd(?P<number>\d+)(?P<suffix>.*)\.dat", re.IGNORECASE)
evaluated_filename_pattern = re.compile(r"a_pd(?P<number>\d+)(?P<suffix>.*)\.dat", re.IGNORECASE)
date_pattern = re.compile(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})")
def get_data_from_file(number):
    u"""Find the datafiles for a given PDS number, and return all data found in
    them.  The resulting dictionary may contain the following keys:
    ``"raw_datafile"``, ``"evaluated_datafile"``, ``"timestamp"``,
    ``"number"``, and ``"comments"``.  This is ready to be used as the
    ``initial`` keyword parameter of a `PDSMeasurementForm`.  Moreover, it
    looks for the sample that was measured in the database, and if it finds it,
    returns it, too.

    :Parameters:
      - `number`: the PDS number of the PDS measurement

    :type number: int

    :Return:
      a dictionary with all data found in the datafile including the filenames
      for this measurement, and the sample connected with deposition if any.
      If no sample in the database fits, ``None`` is returned as the sample.

    :rtype: dict mapping str to ``object``, `models.Sample`
    """
    # First step: find the files
    raw_filename = evaluated_filename = None
    for directory, __, filenames in os.walk(root_dir, topdown=False):
        for filename in filenames:
            if raw_filename and evaluated_filename:
                break
            if not raw_filename:
                match = raw_filename_pattern.match(filename)
                if match and match.group("prefix").lower() != "a_" and int(match.group("number")) == number:
                    raw_filename = os.path.join(directory, filename)
                    continue
            if not evaluated_filename:
                match = evaluated_filename_pattern.match(filename)
                if match and int(match.group("number")) == number:
                    evaluated_filename = os.path.join(directory, filename)
        if raw_filename and evaluated_filename:
            break
    # Second step: parse the raw data file and populate the resulting
    # dictionary
    result = {}
    sample = None
    comment_lines = []
    if raw_filename:
        result["raw_datafile"] = raw_filename[len(root_dir):]
        try:
            for linenumber, line in enumerate(codecs.open(raw_filename, encoding="cp1252")):
                linenumber += 1
                line = line.strip()
                if (linenumber > 5 and line.startswith("BEGIN")) or linenumber >= 21:
                    break
                if linenumber == 1:
                    match = date_pattern.match(line)
                    if match:
                        file_timestamp = datetime.datetime.fromtimestamp(os.stat(raw_filename).st_mtime)
                        data_timestamp = datetime.datetime(
                            int(match.group("year")), int(match.group("month")), int(match.group("day")), 10, 0)
                        if file_timestamp.date() == data_timestamp.date():
                            result["timestamp"] = file_timestamp
                        else:
                            result["timestamp"] = data_timestamp
                elif linenumber == 2:
                    try:
                        sample_name = utils.normalize_legacy_sample_name(line)
                        sample = models.Sample.objects.get(name=sample_name)
                    except (ValueError, models.Sample.DoesNotExist):
                        pass
                elif linenumber >= 5:
                    comment_lines.append(line)
        except IOError:
            pass
    comments = u"\n".join(comment_lines) + "\n"
    while "\n\n" in comments:
        comments = comments.replace("\n\n", "\n")
    if comments.startswith("\n"):
        comments = comments[1:]
    result["comments"] = comments
    if evaluated_filename:
        result["evaluated_datafile"] = evaluated_filename[len(root_dir):]
    result["number"] = unicode(number)
    return result, sample

class SampleForm(forms.Form):
    u"""Form for the sample selection field.  You can only select *one* sample
    per PDS measurement (in contrast to depositions).
    """
    _ = ugettext_lazy
    sample = form_utils.SampleField(label=_(u"Sample"))
    def __init__(self, user_details, pds_measurement, preset_sample, *args, **kwargs):
        u"""Form constructor.  I only set the selection of samples to the
        current user's “My Samples”.

        :Parameters:
          - `user_details`: the details of the current user
          - `pds_measurement`: the PDS measurement to be edited, or ``None`` if
            a new is about to be created
          - `preset_sample`: the sample to which the PDS measurement should be
            appended when creating a new PDS measurement; see
            `utils.extract_preset_sample`

        :type user_details: `models.UserDetails`
        :type pds_measurement: `models.PDSMeasurement`
        :type preset_sample: `models.Sample`
        """
        super(SampleForm, self).__init__(*args, **kwargs)
        samples = list(user_details.my_samples.all())
        if pds_measurement:
            samples.extend(pds_measurement.samples.all()[:1])
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample"].initial = preset_sample.pk
        self.fields["sample"].set_samples(samples)
    
class PDSMeasurementForm(form_utils.ProcessForm):
    u"""Model form for the core PDS measurement data.  I only redefine the
    ``operator`` field here in oder to have the full names of the users.
    """
    _ = ugettext_lazy
    operator = form_utils.FixedOperatorField(label=_(u"Operator"))
    def __init__(self, user, *args, **kwargs):
        u"""Form constructor.  I just adjust layout here.
        """
        super(PDSMeasurementForm, self).__init__(*args, **kwargs)
        self.fields["raw_datafile"].widget.attrs["size"] = self.fields["evaluated_datafile"].widget.attrs["size"] = "50"
        self.fields["number"].widget.attrs["size"] = "10"
        self.fields["operator"].set_operator(kwargs["instance"].operator if kwargs.get("instance") else user)
    def test_for_datafile(self, filename):
        u"""Test whether a certain file is openable by Chantal.

        :Parameters:
          - `filename`: Path to the file to be tested.  Note that this is a
            relative path: The `root_dir` is implicitly prepended to the
            filename.

        :type filename: str

        :Return:
          wheter the file could be opened for reading

        :rtype: bool
        """
        if filename:
            try:
                open(os.path.join(root_dir, filename))
            except IOError:
                raise ValidationError(_(u"Couldn't open datafile."))
    def clean_raw_datafile(self):
        u"""Check whether the raw datafile name points to a readable file.
        """
        filename = self.cleaned_data["raw_datafile"]
        self.test_for_datafile(filename)
        return filename
    def clean_evaluated_datafile(self):
        u"""Check whether the evaluated datafile name points to a readable
        file.
        """
        filename = self.cleaned_data["evaluated_datafile"]
        self.test_for_datafile(filename)
        return filename
    def validate_unique(self):
        u"""Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in `edit`.  I cannot use Django's built-in test anyway
        because it leads to an error message in wrong German (difficult to fix,
        even for the Django guys).
        """
        pass
    class Meta:
        model = models.PDSMeasurement
        exclude = ("external_operator",)

class OverwriteForm(forms.Form):
    u"""Form for the checkbox whether the form data should be taken from the
    datafile.
    """
    _ = ugettext_lazy
    overwrite_from_file = forms.BooleanField(label=_(u"Overwrite with file data"), required=False)

class RemoveFromMySamplesForm(forms.Form):
    u"""Form for the question whether the user wants to remove the measured
    sample from the “My Samples” list after having created the deposition.
    """
    _ = ugettext_lazy
    remove_measured_from_my_samples = forms.BooleanField(label=_(u"Remove measured sample from My Samples"),
                                                         required=False, initial=True)

def is_all_valid(pds_measurement_form, sample_form, overwrite_form, remove_from_my_samples_form):
    u"""Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :Parameters:
      - `pds_measurement_form`: a bound PDS measurement form
      - `sample_form`: a bound sample selection form
      - `overwrite_form`: a bound overwrite data form
      - `remove_from_my_samples_form`: a bound remove-from-my-samples form

    :type pds_measurement_form: `PDSMeasurementForm`
    :type sample_form: `SampleForm`
    :type overwrite_form: `OverwriteForm`
    :type remove_from_my_samples_form: `RemoveFromMySamplesForm`

    :Return:
      whether all forms are valid, i.e. their ``is_valid`` method returns
      ``True``.

    :rtype: bool
    """
    all_valid = pds_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    all_valid = overwrite_form.is_valid() and all_valid
    all_valid = remove_from_my_samples_form.is_valid() and all_valid
    return all_valid

def is_referentially_valid(pds_measurement_form, sample_form, pds_number):
    u"""Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :Parameters:
      - `pds_measurement_form`: a bound PDS measurement form
      - `sample_form`: a bound sample selection form
      - `pds_number`: The PDS number of the PDS measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.

    :type pds_measurement_form: `PDSMeasurementForm`
    :type sample_form: `SampleForm`
    :type pds_number: unicode
    
    :Return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if pds_measurement_form.is_valid():
        number = pds_measurement_form.cleaned_data["number"]
        if unicode(number) != pds_number and models.PDSMeasurement.objects.filter(number=number).count():
            form_utils.append_error(pds_measurement_form, _(u"This PDS number is already in use."))
            referentially_valid = False
        if sample_form.is_valid() and form_utils.dead_samples([sample_form.cleaned_data["sample"]],
                                                              pds_measurement_form.cleaned_data["timestamp"]):
            form_utils.append_error(pds_measurement_form, _(u"Sample is already dead at this time."), "timestamp")
            referentially_valid = False
    return referentially_valid
    
    
@login_required
def edit(request, pds_number):
    u"""Edit and create view for PDS measurements.

    :Parameters:
      - `request`: the current HTTP Request object
      - `pds_number`: The PDS number of the PDS measurement to be edited.  If
        it is ``None``, a new measurement is added to the database. 

    :type request: ``HttpRequest``
    :type pds_number: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    pds_measurement = get_object_or_404(models.PDSMeasurement, number=utils.convert_id_to_int(pds_number)) \
        if pds_number is not None else None
    permissions.assert_can_add_edit_physical_process(request.user, pds_measurement, models.PDSMeasurement)
    user_details = utils.get_profile(request.user)
    preset_sample = utils.extract_preset_sample(request) if not pds_measurement else None
    if request.method == "POST":
        pds_measurement_form = None
        sample_form = SampleForm(user_details, pds_measurement, preset_sample, request.POST)
        remove_from_my_samples_form = RemoveFromMySamplesForm(request.POST)
        overwrite_form = OverwriteForm(request.POST)
        if overwrite_form.is_valid() and overwrite_form.cleaned_data["overwrite_from_file"]:
            try:
                number = int(request.POST["number"])
            except (ValueError, KeyError):
                pass
            else:
                initial, sample = get_data_from_file(number)
                try:
                    initial["operator"] = int(request.POST["operator"])
                except (ValueError, KeyError):
                    pass
                if sample:
                    user_details.my_samples.add(sample)
                pds_measurement_form = PDSMeasurementForm(request.user, instance=pds_measurement, initial=initial)
                overwrite_form = OverwriteForm()
        if pds_measurement_form is None:
            pds_measurement_form = PDSMeasurementForm(request.user, request.POST, instance=pds_measurement)
        all_valid = is_all_valid(pds_measurement_form, sample_form, overwrite_form, remove_from_my_samples_form)
        referentially_valid = is_referentially_valid(pds_measurement_form, sample_form, pds_number)
        if all_valid and referentially_valid:
            pds_measurement = pds_measurement_form.save()
            samples = [sample_form.cleaned_data["sample"]]
            pds_measurement.samples = samples
            if remove_from_my_samples_form.cleaned_data["remove_measured_from_my_samples"]:
                utils.remove_samples_from_my_samples(samples, user_details)
            success_report = _(u"%s was successfully changed in the database.") % pds_measurement if pds_number else \
                _(u"%s was successfully added to the database.") % pds_measurement
            return utils.successful_response(request, success_report, remote_client_response=pds_measurement.pk)
    else:
        initial = {}
        if pds_number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            numbers = models.PDSMeasurement.objects.values_list("number", flat=True)
            initial["number"] = max(numbers) + 1 if numbers else 1
        pds_measurement_form = PDSMeasurementForm(request.user, instance=pds_measurement, initial=initial)
        initial = {}
        if pds_measurement:
            samples = pds_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = SampleForm(user_details, pds_measurement, preset_sample, initial=initial)
        overwrite_form = OverwriteForm()
        remove_from_my_samples_form = RemoveFromMySamplesForm()
    title = _(u"PDS measurement %s") % pds_number if pds_number else _(u"Add PDS measurement")
    return render_to_response("edit_pds_measurement.html", {"title": title,
                                                            "pds_measurement": pds_measurement_form,
                                                            "overwrite": overwrite_form,
                                                            "sample": sample_form,
                                                            "remove_from_my_samples": remove_from_my_samples_form},
                              context_instance=RequestContext(request))
