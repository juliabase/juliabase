#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collected views for dealing with sample series.

Names of sample series are of the form ``originator-YY-name``, where
``originator`` is the person who created the sample series, and ``YY`` is the
year (two digits). ``name`` is almost arbitrary.  Names of sample series can't
be changed once they have been created.
"""

import datetime
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models, permissions
from django.forms import Form, ModelChoiceField
import django.core.urlresolvers
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
import django.contrib.auth.models
from django.utils.http import urlquote_plus
from chantal.samples.views import utils, form_utils, feed_utils

class SampleSeriesForm(Form):
    u"""Form for editing and creating sample series.
    """
    _ = ugettext_lazy
    name = forms.CharField(label=_(u"Name"), max_length=50)
    currently_responsible_person = form_utils.UserField(label=_(u"Currently responsible person"))
    group = form_utils.GroupField(label=_(u"Group"))
    samples = form_utils.MultipleSamplesField(label=_(u"Samples"))
    def __init__(self, user_details, sample_series, data=None, **kwargs):
        u"""Form constructor.  I have to initialise the form here, especially
        because the sample set to choose from must be found and the name of an
        existing series must not be changed.
        """
        super(SampleSeriesForm, self).__init__(data, **kwargs)
        samples = user_details.my_samples.all()
        if sample_series:
            samples = list(samples) + list(sample_series.samples.all())
        self.fields["samples"].set_samples(samples)
        self.fields["samples"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
        self.fields["name"].widget.attrs.update({"size": "50"})
        if sample_series:
            self.fields["name"].required = False
        self.fields["currently_responsible_person"].set_users(
            sample_series.currently_responsible_person if sample_series else None)
        self.fields["group"].set_groups(sample_series.group if sample_series else None)

@login_required
def show(request, name):
    u"""View for showing a sample series.  You can see a sample series if
    you're in its group, or you're the currently responsible person for it, or
    if you can view all samples anyway.
    
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
    user_details = utils.get_profile(request.user)
    result_processes = utils.ResultContext(request.user, sample_series).collect_processes()
    can_edit = permissions.has_permission_to_edit_sample_series(request.user, sample_series)
    can_add_result = permissions.has_permission_to_add_result_process(request.user, sample_series)
    return render_to_response("show_sample_series.html",
                              {"title": _(u"Sample series “%s”") % sample_series.name,
                               "can_edit": can_edit, "can_add_result": can_add_result,
                               "sample_series": sample_series,
                               "result_processes": result_processes},
                              context_instance=RequestContext(request))

def is_referentially_valid(sample_series, sample_series_form, edit_description_form):
    u"""Checks that the “important” checkbox is marked if the group or the
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
    cleaned_data = sample_series_form.cleaned_data
    if sample_series_form.is_valid() and edit_description_form.is_valid() and \
            (cleaned_data["group"] != sample_series.group or
             cleaned_data["currently_responsible_person"] != sample_series.currently_responsible_person) and \
             not edit_description_form.cleaned_data["important"]:
        referentially_valid = False
        form_utils.append_error(edit_description_form,
                                _(u"Changing the group or the responsible person must be marked as important."), "important")
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
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(user_details, sample_series, request.POST)
        edit_description_form = form_utils.EditDescriptionForm(request.POST)
        all_valid = sample_series_form.is_valid()
        all_valid = edit_description_form.is_valid() and all_valid
        referentially_valid = is_referentially_valid(sample_series, sample_series_form, edit_description_form)
        if all_valid and referentially_valid:
            edit_description = edit_description_form.cleaned_data
            feed_reporter = feed_utils.Reporter(request.user)
            if sample_series.currently_responsible_person != sample_series_form.cleaned_data["currently_responsible_person"]:
                sample_series.currently_responsible_person = sample_series_form.cleaned_data["currently_responsible_person"]
                feed_reporter.report_new_responsible_person_sample_series(sample_series, edit_description)
            old_group = sample_series.group
            if old_group != sample_series_form.cleaned_data["group"]:
                sample_series.group = sample_series_form.cleaned_data["group"]
                feed_reporter.report_changed_sample_series_group(sample_series, old_group, edit_description)
            sample_series.save()
            feed_reporter.report_edited_sample_series(sample_series, edit_description)
            sample_series.samples = sample_series_form.cleaned_data["samples"]
            feed_reporter.report_edited_sample_series(sample_series, edit_description)
            request.session["success_report"] = \
                _(u"Sample series %s was successfully updated in the database.") % sample_series.name
            return utils.HttpResponseSeeOther(sample_series.get_absolute_url())
    else:
        sample_series_form = \
            SampleSeriesForm(user_details, sample_series,
                             initial={"name": sample_series.name.split("-", 2)[-1],
                                      "currently_responsible_person":
                                          sample_series.currently_responsible_person._get_pk_val(),
                                      "group": sample_series.group._get_pk_val(),
                                      "samples": [sample._get_pk_val() for sample in sample_series.samples.all()]})
        edit_description_form = form_utils.EditDescriptionForm()
    result_processes = utils.ResultContext(request.user, sample_series).collect_processes()
    return render_to_response("edit_sample_series.html",
                              {"title": _(u"Edit sample series “%s”") % sample_series.name,
                               "sample_series": sample_series_form,
                               "is_new": False,
                               "edit_description": edit_description_form,
                               "result_processes": result_processes},
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
    user_details = utils.get_profile(request.user)
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(user_details, None, request.POST)
        if sample_series_form.is_valid():
            timestamp = datetime.datetime.today()
            full_name = \
                u"%s-%02d-%s" % (request.user.username, timestamp.year % 100, sample_series_form.cleaned_data["name"])
            if models.SampleSeries.objects.filter(name=full_name).count():
                form_utils.append_error(sample_series_form, _("This sample series name is already given."), "name")
            else:
                sample_series = models.SampleSeries(name=full_name, timestamp=timestamp,
                                                    currently_responsible_person= \
                                                        sample_series_form.cleaned_data["currently_responsible_person"],
                                                    group=sample_series_form.cleaned_data["group"])
                sample_series.save()
                sample_series.samples=sample_series_form.cleaned_data["samples"]
                feed_utils.Reporter(request.user).report_new_sample_series(sample_series)
                request.session["success_report"] = \
                    _(u"Sample series %s was successfully added to the database.") % full_name
                return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.main.main_menu"))
    else:
        sample_series_form = SampleSeriesForm(user_details, None)
    return render_to_response("edit_sample_series.html",
                              {"title": _(u"Create new sample series"),
                               "sample_series": sample_series_form,
                               "is_new": True,
                               "name_prefix": u"%s-%02d" % (request.user.username, datetime.datetime.today().year % 100)},
                              context_instance=RequestContext(request))
