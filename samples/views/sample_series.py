#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collected views for dealing with sample series.

Names of sample series are of the form ``originator-YY-name``, where
``originator`` is the person who created the sample series, and ``YY`` is the
year (two digits). ``name`` is almost arbitrary.  Names of sample series can't
be changed once they have been created.
"""

from __future__ import absolute_import

import datetime
from django.views.decorators.http import condition
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from samples import models, permissions
import django.core.urlresolvers
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy, ungettext
from django.forms.util import ValidationError
import django.contrib.auth.models
from django.utils.http import urlquote_plus
import chantal_common.utils
from chantal_common.utils import append_error, adjust_timezone_information
from samples.views import utils, form_utils, feed_utils, csv_export


class SampleSeriesForm(forms.ModelForm):
    u"""Form for editing and creating sample series.
    """
    _ = ugettext_lazy
    short_name = forms.CharField(label=_(u"Name"), max_length=50)
    currently_responsible_person = form_utils.UserField(label=_(u"Currently responsible person"))
    topic = form_utils.TopicField(label=_(u"Topic"))
    samples = form_utils.MultipleSamplesField(label=_(u"Samples"))

    def __init__(self, user, data=None, **kwargs):
        u"""Form constructor.  I have to initialise the form here, especially
        because the sample set to choose from must be found and the name of an
        existing series must not be changed.
        """
        super(SampleSeriesForm, self).__init__(data, **kwargs)
        sample_series = kwargs.get("instance")
        samples = user.my_samples.all()
        if sample_series:
            samples = list(samples) + list(sample_series.samples.all())
        self.fields["samples"].set_samples(samples)
        self.fields["samples"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
        self.fields["short_name"].widget.attrs.update({"size": "50"})
        if sample_series:
            self.fields["short_name"].required = False
        if sample_series:
            self.fields["currently_responsible_person"].set_users(sample_series.currently_responsible_person)
        else:
            self.fields["currently_responsible_person"].choices = ((user.pk, unicode(user)),)
        self.fields["topic"].set_topics(user, sample_series.topic if sample_series else None)

    def clean_description(self):
        u"""Forbid image and headings syntax in Markdown markup.
        """
        description = self.cleaned_data["description"]
        chantal_common.utils.check_markdown(description)
        return description

    def validate_unique(self):
        u"""Overridden to disable Django's intrinsic test for uniqueness.  I
        simply disable this inherited method completely because I do my own
        uniqueness test in the create view itself.  I cannot use Django's
        built-in test anyway because it leads to an error message in wrong
        German (difficult to fix, even for the Django guys).
        """
        pass

    class Meta:
        model = models.SampleSeries
        exclude = ("timestamp", "results", "name")


def sample_series_timestamp(request, name):
    u"""Check whether the sample series datasheet can be taken from the browser
    cache.  For this, the timestamp of last modification of the sample series
    is taken, and that of other things that influence the sample datasheet
    (e.g. language).  The later timestamp is chosen and returned.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the sample series

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the timestamp of the last modification of the sample's datasheet

    :rtype: ``datetime.datetime``
    """
    if not hasattr(request, "_sample_series_timestamp"):
        try:
            sample_series = models.SampleSeries.objects.get(name=name)
        except models.SampleSeries.DoesNotExist:
            return None
        timestamp = max(sample_series.last_modified, request.user.samples_user_details.display_settings_timestamp)
        request._sample_series_timestamp adjust_timezone_information(timestamp)


def sample_series_timestamp(request, name):
    u"""Calculate the timestamp of a sample series.  See
    `sample.sample_timestamp` for further information.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the sample series

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the timestamp of the last modification of the sample series' datasheet

    :rtype: ``datetime.datetime``
    """
    embed_timestamp(request, name)
    return request._sample_series_timestamp


def sample_series_etag(request, name):
    u"""Calculate an ETag for the sample series page.  See
    `sample.sample_timestamp` for further information.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the sample series

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the ETag of the sample series' page

    :rtype: str
    """
    embed_timestamp(request, name)
    hash_ = hashlib.sha1()
    hash_.update(str(request._sample_series_timestamp))
    hash_.update(str(request.user.pk))
    return hash_.hexdigest()


@login_required
@condition(sample_series_etag, sample_series_timestamp)
def show(request, name):
    u"""View for showing a sample series.  You can see a sample series if
    you're in its topic, or you're the currently responsible person for it,
    or if you can view all samples anyway.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: name of the sample series

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample_series = get_object_or_404(models.SampleSeries, name=name)
    permissions.assert_can_view_sample_series(request.user, sample_series)
    user_details = request.user.samples_user_details
    result_processes = [utils.digest_process(result, request.user) for result in sample_series.results.all()]
    can_edit = permissions.has_permission_to_edit_sample_series(request.user, sample_series)
    can_add_result = permissions.has_permission_to_add_result_process(request.user, sample_series)
    return render_to_response("samples/show_sample_series.html",
                              {"title": _(u"Sample series “%s”") % sample_series.name,
                               "can_edit": can_edit, "can_add_result": can_add_result,
                               "sample_series": sample_series,
                               "result_processes": result_processes},
                              context_instance=RequestContext(request))


def is_referentially_valid(sample_series, sample_series_form, edit_description_form):
    u"""Checks that the “important” checkbox is marked if the topic or the
    currently responsible person were changed.

    :Parameters:
      - `sample_series`: the currently edited sample series
      - `sample_series_form`: the bound sample series form
      - `edit_description_form`: a bound form with description of edit changes

    :type sample_series: `models.SampleSeries`
    :type sample_series_form: `SampleSeriesForm`
    :type edit_description_form: `form_utils.EditDescriptionForm`

    :Return:
      whether the “important” tickbox was really marked in case of significant
      changes

    :rtype: bool
    """
    referentially_valid = True
    if sample_series_form.is_valid() and edit_description_form.is_valid() and \
            (sample_series_form.cleaned_data["topic"] != sample_series.topic or
             sample_series_form.cleaned_data["currently_responsible_person"] !=
             sample_series.currently_responsible_person) and \
             not edit_description_form.cleaned_data["important"]:
        referentially_valid = False
        append_error(edit_description_form,
                     _(u"Changing the topic or the responsible person must be marked as important."), "important")
    return referentially_valid


@login_required
def edit(request, name):
    u"""View for editing an existing sample series.  Only the currently
    responsible person can edit a sample series.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: name of the sample series

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample_series = get_object_or_404(models.SampleSeries, name=name)
    permissions.assert_can_edit_sample_series(request.user, sample_series)
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(request.user, request.POST, instance=sample_series)
        edit_description_form = form_utils.EditDescriptionForm(request.POST)
        all_valid = sample_series_form.is_valid()
        all_valid = edit_description_form.is_valid() and all_valid
        referentially_valid = is_referentially_valid(sample_series, sample_series_form, edit_description_form)
        if all_valid and referentially_valid:
            edit_description = edit_description_form.cleaned_data
            feed_reporter = feed_utils.Reporter(request.user)
            if sample_series.currently_responsible_person != sample_series_form.cleaned_data["currently_responsible_person"]:
                feed_reporter.report_new_responsible_person_sample_series(sample_series, edit_description)
            if sample_series.topic != sample_series_form.cleaned_data["topic"]:
                feed_reporter.report_changed_sample_series_topic(sample_series, sample_series.topic, edit_description)
            feed_reporter.report_edited_sample_series(sample_series, edit_description)
            sample_series = sample_series_form.save()
            feed_reporter.report_edited_sample_series(sample_series, edit_description)
            return utils.successful_response(
                request, _(u"Sample series %s was successfully updated in the database.") % sample_series.name)
    else:
        sample_series_form = \
            SampleSeriesForm(request.user, instance=sample_series,
                             initial={"short_name": sample_series.name.split("-", 2)[-1],
                                      "currently_responsible_person": sample_series.currently_responsible_person.pk,
                                      "topic": sample_series.topic.pk,
                                      "samples": [sample.pk for sample in sample_series.samples.all()]})
        edit_description_form = form_utils.EditDescriptionForm()
    return render_to_response("samples/edit_sample_series.html",
                              {"title": _(u"Edit sample series “%s”") % sample_series.name,
                               "sample_series": sample_series_form,
                               "is_new": False, "edit_description": edit_description_form},
                              context_instance=RequestContext(request))


@login_required
def new(request):
    u"""View for creating a new sample series.  Note that you can add arbitrary
    samples to a sample series, even those you can't see.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(request.user, request.POST)
        if sample_series_form.is_valid():
            timestamp = datetime.datetime.today()
            full_name = \
                u"%s-%02d-%s" % (request.user.username, timestamp.year % 100, sample_series_form.cleaned_data["short_name"])
            if models.SampleSeries.objects.filter(name=full_name).exists():
                append_error(sample_series_form, _("This sample series name is already given."), "short_name")
            elif len(full_name) > models.SampleSeries._meta.get_field("name").max_length:
                overfull_letters = len(full_name) - models.SampleSeries._meta.get_field("name").max_length
                error_message = ungettext("The name is %d letter too long.", "The name is %d letters too long.",
                                          overfull_letters) % overfull_letters
                append_error(sample_series_form, error_message, "short_name")
            else:
                sample_series = sample_series_form.save(commit=False)
                sample_series.name = full_name
                sample_series.timestamp = timestamp
                sample_series.save()
                sample_series_form.save_m2m()
                feed_utils.Reporter(request.user).report_new_sample_series(sample_series)
                return utils.successful_response(request,
                                                 _(u"Sample series %s was successfully added to the database.") % full_name)
    else:
        sample_series_form = SampleSeriesForm(request.user)
    return render_to_response("samples/edit_sample_series.html",
                              {"title": _(u"Create new sample series"),
                               "sample_series": sample_series_form,
                               "is_new": True,
                               "name_prefix": u"%s-%02d" % (request.user.username, datetime.datetime.today().year % 100)},
                              context_instance=RequestContext(request))


@login_required
def export(request, name):
    u"""View for exporting a sample series to CSV data.  Thus, the return value
    is not an HTML response but a text/csv response.  Note that you must also
    be allowed to see all *samples* in this sample series for CSV table export.

    :Parameters:
      - `request`: the current HTTP Request object
      - `name`: the name of the sample series

    :type request: ``HttpRequest``
    :type name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample_series = get_object_or_404(models.SampleSeries, name=name)
    permissions.assert_can_view_sample_series(request.user, sample_series)
    for sample in sample_series.samples.all():
        permissions.assert_can_fully_view_sample(request.user, sample)
    return csv_export.export(request, sample_series.get_data(), _(u"sample"), renaming_offset=2)
