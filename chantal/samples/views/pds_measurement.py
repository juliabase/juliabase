#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime, os.path, re, codecs
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
import django.contrib.auth.models
from chantal.samples.views import utils
from chantal.samples.views.utils import check_permission
from chantal.samples import models
from chantal import settings

root_dir = "/home/bronger/temp/pds" if settings.IS_TESTSERVER else "/windows/T/daten/pds"
raw_filename_pattern = re.compile(r"(?P<prefix>.*)pd(?P<number>\d+)(?P<suffix>.*)\.dat", re.IGNORECASE)
evaluated_filename_pattern = re.compile(r"a_pd(?P<number>\d+)(?P<suffix>.*)\.dat", re.IGNORECASE)
date_pattern = re.compile(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})")
def get_data_from_file(number):
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
    result = {}
    sample = None
    comment_lines = []
    if raw_filename:
        result["raw_datafile"] = raw_filename
        try:
            for linenumber, line in enumerate(codecs.open(raw_filename, encoding="cp1252")):
                linenumber += 1
                line = line.strip()
                if (linenumber > 5 and line.startswith("BEGIN")) or linenumber >= 21:
                    break
                if linenumber == 1:
                    match = date_pattern.match(line)
                    if match:
                        file_timestamp = datetime.datetime.fromtimestamp(os.stat(raw_filename)[8])
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
        result["evaluated_datafile"] = evaluated_filename
    result["number"] = unicode(number)
    return result, sample

class SampleForm(forms.Form):
    _ = ugettext_lazy
    sample = forms.ModelChoiceField(label=_(u"Sample"), queryset=None)
    def __init__(self, user_details, *args, **keyw):
        super(SampleForm, self).__init__(*args, **keyw)
        self.fields["sample"].queryset = user_details.my_samples
    
class PDSMeasurementForm(forms.ModelForm):
    _ = ugettext_lazy
    operator = utils.OperatorChoiceField(label=_(u"Operator"), queryset=django.contrib.auth.models.User.objects.all())
    class Meta:
        model = models.PDSMeasurement
        exclude = ("external_operator",)

class OverwriteForm(forms.Form):
    _ = ugettext_lazy
    overwrite_from_file = forms.BooleanField(label=_(u"overwrite with file data"), required=False)

def is_all_valid(pds_measurement_form, sample_form, overwrite_form):
    all_valid = pds_measurement_form.is_valid()
    all_valid = sample_form.is_valid() and all_valid
    all_valid = overwrite_form.is_valid() and all_valid
    return all_valid
    
@login_required
@check_permission("change_pdsmeasurement")
def edit(request, pd_number):
    pds_measurement = get_object_or_404(models.PDSMeasurement, number=utils.convert_id_to_int(pd_number)) \
        if pd_number is not None else None
    user_details = request.user.get_profile()
    if request.method == "POST":
        pds_measurement_form = None
        sample_form = SampleForm(user_details, request.POST)
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
                pds_measurement_form = PDSMeasurementForm(instance=pds_measurement, initial=initial)
                overwrite_form = OverwriteForm()
        if pds_measurement_form is None:
            pds_measurement_form = PDSMeasurementForm(request.POST, instance=pds_measurement)
        if is_all_valid(pds_measurement_form, sample_form, overwrite_form):
            pds_measurement = pds_measurement_form.save()
            pds_measurement.samples = [sample_form.cleaned_data["sample"]]
            return utils.http_response_go_next(request)
    else:
        initial = {}
        if pd_number is None:
            initial = {"timestamp": datetime.datetime.now(), "operator": request.user.pk}
            numbers = models.PDSMeasurement.objects.values_list("number", flat=True)
            initial["number"] = max(numbers) + 1 if numbers else 1
        pds_measurement_form = PDSMeasurementForm(instance=pds_measurement, initial=initial)
        initial = {}
        if pds_measurement:
            samples = pds_measurement.samples.all()
            if samples:
                initial["sample"] = samples[0].pk
        sample_form = SampleForm(user_details, initial=initial)
        overwrite_form = OverwriteForm()
    return render_to_response("edit_pds_measurement.html", {"pds_measurement": pds_measurement_form,
                                                            "overwrite": overwrite_form,
                                                            "sample": sample_form},
                              context_instance=RequestContext(request))
