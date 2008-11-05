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
            elif chunk.startswith("\xff\xd8\xff\xe0\x00\x10JFIF"):
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

class ResultForm(forms.ModelForm):
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
    def clean_comments(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        comments = self.cleaned_data["comments"]
        form_utils.check_markdown(comments)
        return comments
    class Meta:
        model = models.Result
        exclude = ("timestamp", "timestamp_inaccuracy", "operator", "external_operator", "image_type")

class RelatedDataForm(forms.Form):
    u"""Form for samples, sample series, and the image connected with this
    result process.  Since all these things are not part of the result process
    model itself, they are in a form of its own.  Note that „image file“ is a
    special case here because it's the only editable thing when *editing* a
    view.  In contrast, samples and sample series can only be set when creating
    a new result process.  The non-editability is realised by not showing the
    fields in the template, and by ignoring possibly submitted values when
    writing to the database.
    """
    _ = ugettext_lazy
    samples = forms.ModelMultipleChoiceField(label=_(u"Samples"), queryset=None, required=False)
    sample_series = forms.ModelMultipleChoiceField(label=_(u"Sample serieses"), queryset=None, required=False)
    image_file = forms.FileField(label=_(u"Image file"), required=False)
    def __init__(self, user_details, query_string_dict, data=None, files=None, **kwargs):
        u"""Form constructor.  I have to initialise a couple of things here in
        a non-trivial way.

        The most complicated thing is to find all sample series electable for
        the result.  Note that the current query will probably find to many
        electable sample series, but unallowed series will be rejected by
        `is_referentially_valid` anyway.
        """
        super(RelatedDataForm, self).__init__(data, files, **kwargs)
        if query_string_dict is not None:
            self.fields["samples"].queryset = \
                models.Sample.objects.filter(Q(watchers=user_details) | Q(name=query_string_dict.get("sample"))).distinct()
            if "sample" in query_string_dict:
                try:
                    self.fields["samples"].initial = \
                        [models.Sample.objects.get(name=query_string_dict["sample"])._get_pk_val()]
                except models.Sample.DoesNotExist:
                    raise Http404(u"sample %s given in query string not found" % query_string_dict["sample"])
            now = datetime.datetime.now() + datetime.timedelta(seconds=5)
            three_months_ago = now - datetime.timedelta(days=90)
            self.fields["sample_series"].queryset = \
                models.SampleSeries.objects.filter(Q(samples__watchers=user_details) |
                                                   ( Q(currently_responsible_person=user_details.user) &
                                                     Q(timestamp__range=(three_months_ago, now)))
                                                   | Q(name=query_string_dict.get("sample_series"))).distinct()
            self.fields["sample_series"].initial = [query_string_dict.get("sample_series")]
        self.fields["image_file"].widget.attrs["size"] = 60
    
@login_required
def edit(request, process_id):
    u"""View for editing existing results.

    :Parameters:
      - `request`: the current HTTP Request object
      - `process_id`: the ID of the result process

    :type request: ``HttpRequest``
    :type process_id: str

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_edit_result_process(request.user, result)
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        result_form = ResultForm(request.POST, instance=result)
        related_data_form = RelatedDataForm(user_details, None, request.POST, request.FILES)
        edit_description_form = form_utils.EditDescriptionForm(request.POST)
        all_valid = result_form.is_valid()
        all_valid = related_data_form.is_valid() and all_valid
        all_valid = edit_description_form.is_valid() and all_valid
        if all_valid:
            result_form.save()
            if related_data_form.cleaned_data["image_file"]:
                save_image_file(request.FILES["image_file"], result, related_data_form)
            if related_data_form.is_valid():
                feed_utils.generate_feed_for_result_process(result, request.user, edit_description_form)
                return utils.successful_response(request)
    else:
        result_form = ResultForm(instance=result)
        related_data_form = RelatedDataForm(user_details, None)
        edit_description_form = form_utils.EditDescriptionForm()
    return render_to_response("edit_result.html", {"title": _(u"Edit result"), "is_new": False, "result": result_form,
                                                   "related_data": related_data_form,
                                                   "edit_description": edit_description_form},
                              context_instance=RequestContext(request))

def is_referentially_valid(related_data_form, user):
    u"""Test whether the related_data form is consistent with the database.  In
    particular, it tests whether the user is allowed to add the result to all
    selected samples and sample series.

    :Parameters:
      - `related_data_form`: bound form with all samples and sample series the
        user wants to add the result to

    :type related_data_form: `RelatedDataForm`
    
    :Return:
      whether the form is consistent with the database

    :rtype: bool
    """
    referentially_valid = True
    for sample_or_series in related_data_form.cleaned_data["samples"] + related_data_form.cleaned_data["sample_series"]:
        if not permissions.has_permission_to_add_result_process(user, sample_or_series):
            referentially_valid = False
            form_utils.append_error(related_data_form,
                                    _(u"You don't have the permission to add the result to all selected samples/series."))
    if not related_data_form.cleaned_data["samples"] and not related_data_form.cleaned_data["sample_series"]:
        referentially_valid = False
        form_utils.append_error(related_data_form, _(u"You must select at least one samples/series."))
    return referentially_valid

@login_required
def new(request):
    u"""View for adding a new result.  This routine also contains the full
    code for creating the forms, checking validity with ``is_valid``, and
    saving it to the database (because it's just so trivial for results).

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    user_details = utils.get_profile(request.user)
    query_string_dict = utils.parse_query_string(request)
    if request.method == "POST":
        result_form = ResultForm(request.POST)
        related_data_form = RelatedDataForm(user_details, query_string_dict, request.POST, request.FILES)
        all_valid = result_form.is_valid()
        all_valid = related_data_form.is_valid() and all_valid
        if all_valid and is_referentially_valid(related_data_form, request.user):
            result = result_form.save(commit=False)
            result.operator = request.user
            result.timestamp = datetime.datetime.now()
            result.save()
            if related_data_form.cleaned_data["image_file"]:
                save_image_file(request.FILES["image_file"], result, related_data_form)
            if related_data_form.is_valid():
                result.samples = related_data_form.cleaned_data["samples"]
                result.sample_series = related_data_form.cleaned_data["sample_series"]
                feed_utils.generate_feed_for_result_process(result, request.user, edit_description_form=None)
                return utils.successful_response(request)
            else:
                result.delete()
    else:
        result_form = ResultForm()
        related_data_form = RelatedDataForm(user_details, query_string_dict)
    return render_to_response("edit_result.html", {"title": _(u"New result"), "is_new": True, "result": result_form,
                                                   "related_data": related_data_form},
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
