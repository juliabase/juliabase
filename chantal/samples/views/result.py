#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for editing and creating results (aka result processes).
"""

import datetime, os, shutil, pickle, re
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
        u"""Global clean method for the related data.  I check whether at least
        one sample or sample series was selected, and whether the user is
        allowed to add results to the selected objects.
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

class DimensionsForm(forms.Form):
    _ = ugettext_lazy
    number_of_quantities = forms.IntegerField(label=_(u"Number of quantities"), min_value=0, max_value=100)
    number_of_values = forms.IntegerField(label=_(u"Number of values"), min_value=0, max_value=100)
    def __init__(self, *args, **kwargs):
        if "initial" not in kwargs:
            kwargs["initial"] = {"number_of_quantities": 0, "number_of_values": 0}
        super(DimensionsForm, self).__init__(*args, **kwargs)
        self.fields["number_of_quantities"].widget.attrs.update({"size": 1, "style": "text-align: center"})
        self.fields["number_of_values"].widget.attrs.update({"size": 1, "style": "text-align: center"})

class QuantityForm(forms.Form):
    _ = ugettext_lazy
    quantity = forms.CharField(label=_("Quantity name"), max_length=50)
    def __init__(self, *args, **kwargs):
        super(QuantityForm, self).__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs.update({"size": 10, "style": "font-weight: bold; text-align: center"})

class ValueForm(forms.Form):
    _ = ugettext_lazy
    value = forms.CharField(label=_("Value"), max_length=50, required=False)
    def __init__(self, *args, **kwargs):
        super(ValueForm, self).__init__(*args, **kwargs)
        self.fields["value"].widget.attrs.update({"size": 10})

def forms_from_database(result, request):
    result_form = ResultForm(instance=result)
    query_string_dict = utils.parse_query_string(request) if not result else None
    user_details = utils.get_profile(request.user)
    related_data_form = RelatedDataForm(user_details, query_string_dict, result)
    edit_description_form = form_utils.EditDescriptionForm() if result else None
    return result_form, related_data_form, edit_description_form, \
        DimensionsForm(), DimensionsForm(prefix="previous"), [], []

def forms_from_post_data(result, request):
    post_data = request.POST
    result_form = ResultForm(post_data, instance=result)
    query_string_dict = utils.parse_query_string(request) if not result else None
    user_details = utils.get_profile(request.user)
    related_data_form = RelatedDataForm(user_details, query_string_dict, result, post_data, request.FILES)
    dimensions_form = DimensionsForm(post_data)
    previous_dimensions_form = DimensionsForm(post_data, prefix="previous")
    if previous_dimensions_form.is_valid():
        found_number_of_quantities = previous_dimensions_form.cleaned_data["number_of_quantities"]
        found_number_of_values = previous_dimensions_form.cleaned_data["number_of_values"]
    else:
        found_number_of_quantities, found_number_of_values = 0, 0
    if dimensions_form.is_valid():
        number_of_quantities = dimensions_form.cleaned_data["number_of_quantities"]
        number_of_values = dimensions_form.cleaned_data["number_of_values"]
        found_number_of_quantities = min(found_number_of_quantities, number_of_quantities)
        found_number_of_values = min(found_number_of_values, number_of_values)
    else:
        number_of_quantities, number_of_values = found_number_of_quantities, found_number_of_values
    quantity_forms = []
    for i in range(number_of_quantities):
        quantity_forms.append(
            QuantityForm(post_data, prefix=str(i)) if i < found_number_of_quantities else QuantityForm(prefix=str(i)))
    value_form_lists = []
    for j in range(number_of_values):
        values = []
        for i in range(number_of_quantities):
            if i < found_number_of_quantities and j < found_number_of_values:
                values.append(ValueForm(post_data, prefix="%d_%d" % (i, j)))
            else:
                values.append(ValueForm(prefix="%d_%d" % (i, j)))
        value_form_lists.append(values)
    edit_description_form = form_utils.EditDescriptionForm(post_data) if result else None
    return result_form, related_data_form, edit_description_form, dimensions_form, previous_dimensions_form, \
        quantity_forms, value_form_lists

def is_all_valid(result_form, related_data_form, dimensions_form, previous_dimensions_form,
                 quantity_forms, value_form_lists, edit_description_form):
    u"""Test whether all bound forms are valid.  This routine guarantees that
    all ``is_valid()`` methods are called, even if the first tested form is
    already invalid.

    :Parameters:
      - `result_form`: the bound form with the result process
      - `related_data_form`: the bound form with all samples and sample series
        the result should be connected with
      - `dimensions_form`: the bound form with the number of columns and rows
        in the result values table
      - `previous_dimonesions_form`: the bound form with the number of columns
        and rows from the previous view, in order to see whether they were
        changed
      - `quantity_forms`: The (mostly) bound forms of quantities (the column
        heads in the table).  Those that are newly added are unbound.
      - `value_form_lists`: The (mostly) bound forms of result values in the
        table.  Those that are newly added are unbound.  The outer list are the
        rows, the inner the columns.
      - `edit_description_form`: the bound form with the edit description if
        we're editing an existing result, and ``None`` otherwise

    :type result_form: `ResultForm`
    :type related_data_form: `RelatedDataForm`
    :type dimensions_form: `DimensionsForm`
    :type previous_dimensions_form: `DimensionsForm`
    :type quantity_forms: list of `QuantityForm`
    :type value_form_lists: list of list of `ValueForm`
    :type edit_description_form: `form_utils.EditDescriptionForm` or
      ``NoneType``

    :Return:
      whether all forms are valid

    :rtype: bool
    """
    all_valid = result_form.is_valid()
    all_valid = related_data_form.is_valid() and all_valid
    all_valid = dimensions_form.is_valid() and all_valid
    all_valid = previous_dimensions_form.is_valid() and all_valid
    all_valid = all([form.is_valid() for form in quantity_forms]) and all_valid
    all_valid = all([all([form.is_valid() for form in form_list]) for form_list in value_form_lists]) and all_valid
    if edit_description_form:
        all_valid = edit_description_form.is_valid() and all_valid
    return all_valid

def is_referentially_valid(result, related_data_form, edit_description_form):
    u"""Test whether all forms are consistent with each other and with the
    database.  In particular, I test here whether the “important” checkbox in
    marked if the user has added new samples or sample series to the result.

    :Parameters:
      - `result`: the result we're editing, or ``None`` if we're creating a new
        one
      - `related_data_form`: the bound form with all samples and sample series
        the result should be connected with
      - `edit_description_form`: the bound form with the edit description if
        we're editing an existing result, and ``None`` otherwise

    :type result: `models.Result` or ``NoneType``
    :type related_data_form: `RelatedDataForm`
    :type edit_description_form: `form_utils.EditDescriptionForm` or
      ``NoneType``

    :Return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if result and related_data_form.is_valid() and edit_description_form.is_valid():
        old_related_objects = set(result.samples.all()) | set(result.sample_series.all())
        new_related_objects = set(related_data_form.cleaned_data["samples"] +
                                  related_data_form.cleaned_data["sample_series"])
        if new_related_objects - old_related_objects and not edit_description_form.cleaned_data["important"]:
            form_utils.append_error(
                edit_description_form, _(u"Adding samples or sample series must be marked as important."), "important")
            referentially_valid = False
    return referentially_valid

def is_structure_changed(dimensions_form, previous_dimensions_form):
    if dimensions_form.is_valid() and previous_dimensions_form.is_valid():
        return dimensions_form.cleaned_data["number_of_quantities"] != \
            previous_dimensions_form.cleaned_data["number_of_quantities"] or \
            dimensions_form.cleaned_data["number_of_values"] != \
            previous_dimensions_form.cleaned_data["number_of_values"]
    else:
        # In case of doubt, assume that the structure was changed.
        return True

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
    if request.method == "POST":
        result_form, related_data_form, edit_description_form, dimensions_form, previous_dimensions_form, \
            quantity_forms, value_form_lists = forms_from_post_data(result, request)
        all_valid = is_all_valid(result_form, related_data_form, dimensions_form, previous_dimensions_form,
                                 quantity_forms, value_form_lists, edit_description_form)
        referentially_valid = is_referentially_valid(result, related_data_form, edit_description_form)
        structure_changed = is_structure_changed(dimensions_form, previous_dimensions_form)
        print structure_changed
        if all_valid and referentially_valid and not structure_changed:
            result = save_to_database(request, result, result_form, related_data_form)
            if result:
                feed_utils.Reporter(request.user).report_result_process(
                    result, edit_description_form.cleaned_data if edit_description_form else None)
                return utils.successful_response(request)
        previous_dimensions_form = DimensionsForm(
            initial={"number_of_quantities": dimensions_form.cleaned_data["number_of_quantities"],
                     "number_of_values": dimensions_form.cleaned_data["number_of_values"]}, prefix="previous")
    else:
        result_form, related_data_form, edit_description_form, dimensions_form, previous_dimensions_form, \
            quantity_forms, value_form_lists = forms_from_database(result, request)
    title = _(u"Edit result") if result else _(u"New result")
    return render_to_response("edit_result.html", {"title": title, "result": result_form,
                                                   "related_data": related_data_form,
                                                   "edit_description": edit_description_form,
                                                   "dimensions": dimensions_form,
                                                   "previous_dimensions": previous_dimensions_form,
                                                   "quantities": quantity_forms,
                                                   "value_lists": value_form_lists},
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
