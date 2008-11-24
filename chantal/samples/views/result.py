#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing and creating results (aka result processes).
"""

import datetime, os, shutil
from django.template import RequestContext
from django.http import Http404
import django.forms as forms
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.db.models import Q
from chantal.samples import models, permissions
from chantal.samples.views import utils, form_utils, feed_utils

def save_image_file(image_data, result, related_data_form):
    u"""Saves an uploaded image file stream to its final destination in
    `settings.UPLOADED_RESULT_IMAGES_ROOT`.  If the given result has already an
    image connected with it, it is removed first.

    :Parameters:
      - `image_data`: the file-like object which contains the uploaded data
        stream
      - `result`: The result object for which the image was uploaded.  It is
        not necessary that all its fields are already there.  But it must have
        been written already to the database because the only necessary field
        is the primary key, which I need for the hash digest for generating the
        file names.
      - `related_data_form`: A bound form with the image filename that was
        uploaded.  This is only needed to dumping error messages into it if
        something went wrong.

    :type image_data: ``django.core.files.uploadedfile.InMemoryUploadedFile``
    :type result: `models.Result`
    :type related_data_form: `RelatedDataForm`
    """
    for i, chunk in enumerate(image_data.chunks()):
        if i == 0:
            if chunk.startswith("\211PNG\r\n\032\n"):
                new_image_type = "png"
            elif chunk.startswith("\xff\xd8\xff"):
                new_image_type = "jpeg"
            elif chunk.startswith("%PDF"):
                new_image_type = "pdf"
            else:
                form_utils.append_error(related_data_form, _(u"Invalid file format.  Only PDF, PNG, and JPEG are allowed."),
                                        "image_file")
                return
            if result.image_type != "none" and new_image_type != result.image_type:
                os.remove(result.get_image_locations()["original"])
            result.image_type = new_image_type
            image_locations = result.get_image_locations()
            shutil.rmtree(image_locations["image_directory"], ignore_errors=True)
            destination = open(image_locations["original"], "wb+")
        destination.write(chunk)
    destination.close()
    result.save()

class ResultForm(form_utils.ProcessForm):
    u"""Model form for a result process.  Note that I exclude many fields
    because they are not used in results or explicitly set.

    FixMe: Possibly, the external operator should be made editable for result
    processes.
    """
    _ = ugettext_lazy
    def __init__(self, *args, **kwargs):
        super(ResultForm, self).__init__(*args, **kwargs)
        self.fields["comments"].required = True
        self.fields["title"].widget.attrs["size"] = 40
    class Meta:
        model = models.Result
        exclude = ("timestamp", "timestamp_inaccuracy", "operator", "external_operator", "image_type")

class RelatedDataForm(forms.Form):
    u"""Form for samples, sample series, and the image connected with this
    result process.  Since all these things are not part of the result process
    model itself, they are in a form of its own.
    """
    _ = ugettext_lazy
    samples = form_utils.MultipleSamplesField(label=_(u"Samples"), required=False)
    sample_series = forms.ModelMultipleChoiceField(label=_(u"Sample serieses"), queryset=None, required=False)
    image_file = forms.FileField(label=_(u"Image file"), required=False)
    def __init__(self, user_details, query_string_dict, old_result, data=None, files=None, **kwargs):
        u"""Form constructor.  I have to initialise a couple of things here in
        a non-trivial way.

        The most complicated thing is to find all sample series electable for
        the result.  Note that the current query will probably find to many
        electable sample series, but unallowed series will be rejected by
        `clean` anyway.
        """
        super(RelatedDataForm, self).__init__(data, files, **kwargs)
        self.old_relationships = set(old_result.samples.all()) | set(old_result.sample_series.all()) if old_result else set()
        self.user = user_details.user
        now = datetime.datetime.now() + datetime.timedelta(seconds=5)
        three_months_ago = now - datetime.timedelta(days=90)
        samples = list(user_details.my_samples.all())
        if old_result:
            samples.extend(old_result.samples.all())
            self.fields["sample_series"].queryset = \
                models.SampleSeries.objects.filter(
                Q(samples__watchers=user_details) | ( Q(currently_responsible_person=user_details.user) &
                                                      Q(timestamp__range=(three_months_ago, now)))
                | Q(pk__in=old_result.sample_series.values_list("pk", flat=True))).distinct()
            self.fields["samples"].initial = old_result.samples.values_list("pk", flat=True)
            self.fields["sample_series"].initial = old_result.sample_series.values_list("pk", flat=True)
        else:
            if "sample" in query_string_dict:
                preset_sample = get_object_or_404(models.Sample, name=query_string_dict["sample"])
                self.fields["samples"].initial = [preset_sample.pk]
                samples.append(preset_sample)
            self.fields["sample_series"].queryset = \
                models.SampleSeries.objects.filter(Q(samples__watchers=user_details) |
                                                   ( Q(currently_responsible_person=user_details.user) &
                                                     Q(timestamp__range=(three_months_ago, now)))
                                                   | Q(name=query_string_dict.get("sample_series", u""))).distinct()
            if "sample_series" in query_string_dict:
                self.fields["sample_series"].initial = \
                    [get_object_or_404(models.SampleSeries, name=query_string_dict["sample_series"])]
        self.fields["samples"].set_samples(samples)
        self.fields["image_file"].widget.attrs["size"] = 60
    def clean(self):
        u"""Global clean method for the related data.  Note that this method
        spares us the ``is_referentially_valid`` routine.  I can do this
        because I only need the old result instance for a complete validity
        check, so there needn't be any inter-form check.
        """
        samples = self.cleaned_data.get("samples")
        sample_series = self.cleaned_data.get("sample_series")
        if samples is not None and sample_series is not None:
            for sample_or_series in set(samples + sample_series) - self.old_relationships:
                if not permissions.has_permission_to_add_result_process(self.user, sample_or_series):
                    form_utils.append_error(
                        self, _(u"You don't have the permission to add the result to all selected samples/series."))
            if not samples and not sample_series:
                form_utils.append_error(self, _(u"You must select at least one samples/series."))
        return self.cleaned_data

def is_all_valid(result_form, related_data_form, edit_description_form):
    u"""Test whether all bound forms are valid.  This routine guarantees that
    all ``is_valid()`` methods are called, even if the first tested form is
    already invalid.

    :Parameters:
      - `result_form`: the bound form with the result process
      - `related_data_form`: the bound form with all samples and sample series
        the result should be connected with
      - `edit_description_form`: the bound form with the edit description if
        we're editing an existing result, and ``None`` otherwise

    :type result_form: `ResultForm`
    :type related_data_form: `RelatedDataForm`
    :type edit_description_form: `form_utils.EditDescriptionForm` or
      ``NoneType``

    :Return:
      whether all forms are valid

    :rtype: bool
    """
    all_valid = result_form.is_valid()
    all_valid = related_data_form.is_valid() and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid

def save_to_database(request, result, result_form, related_data_form):
    u"""Save the forms to the database.  One peculiarity here is that I still
    check validity on this routine, namely whether the uploaded image data is
    correct.  If it is not, the error is written to the ``result_form`` and the
    result of this routine is ``None``.

    :Parameters:
      - `request`: the current HTTP Request object
      - `result`: the result we're editing, or ``None`` if we're creating a new
        one
      - `result_form`: the valid bound form with the result process
      - `related_data_form`: the valid bound form with all samples and sample
        series the result should be connected with

    :type request: ``HttpRequest``
    :type result: `models.Result` or ``NoneType``
    :type result_form: `ResultForm`
    :type related_data_form: `RelatedDataForm`

    :Return:
      the created or updated result instance, or ``None`` if the uploaded image
      data was invalid

    :rtype: `models.Result` or ``NoneType``
    """
    if result:
        result_form.save()
    else:
        result = result_form.save(commit=False)
        result.operator = request.user
        result.timestamp = datetime.datetime.now()
        result.save()
    if related_data_form.cleaned_data["image_file"]:
        save_image_file(request.FILES["image_file"], result, related_data_form)
    if related_data_form.is_valid():
        result.samples = related_data_form.cleaned_data["samples"]
        result.sample_series = related_data_form.cleaned_data["sample_series"]
        return result

@login_required
def edit(request, process_id):
    u"""View for editing existing results, and for creating new ones.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the ID of the result process; ``None`` if we're creating
        a new one

    :type request: ``HttpRequest``
    :type process_id: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id)) if process_id else None
    if result:
        permissions.assert_can_edit_result_process(request.user, result)
    query_string_dict = utils.parse_query_string(request) if not result else None
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        result_form = ResultForm(request.POST, instance=result)
        related_data_form = RelatedDataForm(user_details, query_string_dict, result, request.POST, request.FILES)
        edit_description_form = form_utils.EditDescriptionForm(request.POST) if result else None
        if is_all_valid(result_form, related_data_form, edit_description_form):
            result = save_to_database(request, result, result_form, related_data_form)
            if result:
                feed_utils.Reporter(request.user).report_result_process(
                    result, edit_description_form.cleaned_data if edit_description_form else None)
                return utils.successful_response(request)
    else:
        result_form = ResultForm(instance=result)
        related_data_form = RelatedDataForm(user_details, query_string_dict, result)
        edit_description_form = form_utils.EditDescriptionForm() if result else None
    title = _(u"Edit result") if result else _(u"New result")
    return render_to_response("edit_result.html", {"title": title, "result": result_form,
                                                   "related_data": related_data_form,
                                                   "edit_description": edit_description_form},
                              context_instance=RequestContext(request))

@login_required
def show(request, process_id):
    u"""Shows a particular result process.  The main purpose of this view is to
    be able to visit a result directly from a feed entry about a new/edited
    result.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the database ID of the result to show

    :type request: ``HttpRequest``
    :type process_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_result_process(request.user, result)
    template_context = {"title": _(u"Result “%s”") % result.title, "result": result,
                        "samples": result.samples.all(), "sample_series": result.sample_series.all()}
    template_context.update(utils.ResultContext(request.user, sample_series=None).digest_process(result))
    return render_to_response("show_single_result.html", template_context, context_instance=RequestContext(request))
