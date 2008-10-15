#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collected views for dealing with sample series.

Names of sample series are of the form ``YY-originator-name``, where ``YY`` is
the year (two digits), and ``originator`` is the person who created the sample
series. ``name`` is arbitrary.  Names of sample series can't be changed once
they have been created.
"""

import datetime
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response, get_object_or_404
from chantal.samples import models
from django.forms import Form, ModelChoiceField
import django.core.urlresolvers
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from django.db.models import Q
import django.contrib.auth.models
from django.utils.http import urlquote_plus
from chantal.samples.views import utils

class SampleSeriesForm(Form):
    u"""Form for editing and creating sample series.
    """
    _ = ugettext_lazy
    name = forms.CharField(label=_(u"Name"), max_length=40)
    currently_responsible_person = utils.OperatorChoiceField(label=_(u"Currently responsible person"),
                                                             queryset=django.contrib.auth.models.User.objects)
    group = utils.ModelChoiceField(label=_(u"Group"), queryset=django.contrib.auth.models.Group.objects)
    samples = forms.ModelMultipleChoiceField(label=_(u"Samples"), queryset=None, required=False)
    def __init__(self, user_details, sample_series, data=None, **keyw):
        u"""Form constructor.  I have to initialise the form here, especially
        because the sample set to choose from must be found and the name of an
        existing series must not be changed.
        """
        super(SampleSeriesForm, self).__init__(data, **keyw)
        self.fields["samples"].queryset = \
            models.Sample.objects.filter(Q(series=sample_series) | Q(watchers=user_details)).distinct() if sample_series \
            else user_details.my_samples
        self.fields["samples"].widget.attrs.update({"size": "15", "style": "vertical-align: top"})
        self.fields["name"].widget.attrs.update({"size": "50"})
        if sample_series:
            self.fields["name"].required = False

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
    user_details = utils.get_profile(request.user)
    if not utils.has_permission_for_sample_or_series(request.user, sample_series):
        return utils.HttpResponseSeeOther("permission_error")
    result_processes = utils.ResultContext(request.user, sample_series).collect_processes()
    return render_to_response("show_sample_series.html",
                              {"title": _(u"Sample series “%s”") % sample_series.name,
                               "can_edit": sample_series.currently_responsible_person == request.user,
                               "can_add_process":
                                   bool(utils.get_allowed_result_processes(request.user, sample_series=[sample_series])),
                               "sample_series": sample_series,
                               "result_processes": result_processes},
                              context_instance=RequestContext(request))

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
    user_details = utils.get_profile(request.user)
    if sample_series.currently_responsible_person != request.user:
        return utils.HttpResponseSeeOther("permission_error")
    if request.method == "POST":
        sample_series_form = SampleSeriesForm(user_details, sample_series, request.POST)
        if sample_series_form.is_valid():
            sample_series.currently_responsible_person = sample_series_form.cleaned_data["currently_responsible_person"]
            sample_series.group = sample_series_form.cleaned_data["group"]
            sample_series.save()
            sample_series.samples = sample_series_form.cleaned_data["samples"]
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
    result_processes = utils.ResultContext(request.user, sample_series).collect_processes()
    return render_to_response("edit_sample_series.html",
                              {"title": _(u"Edit sample series “%s”") % sample_series.name,
                               "sample_series": sample_series_form,
                               "is_new": False,
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
                u"%02d-%s-%s" % (timestamp.year % 100, request.user.username, sample_series_form.cleaned_data["name"])
            if models.SampleSeries.objects.filter(name=full_name).count():
                utils.append_error(sample_series_form, _("This sample series name is already given."), "name")
            else:
                sample_series = models.SampleSeries(name=full_name, timestamp=timestamp,
                                                    currently_responsible_person= \
                                                        sample_series_form.cleaned_data["currently_responsible_person"],
                                                    group=sample_series_form.cleaned_data["group"])
                sample_series.save()
                sample_series.samples=sample_series_form.cleaned_data["samples"]
                request.session["success_report"] = \
                    _(u"Sample series %s was successfully added to the database.") % full_name
                return utils.HttpResponseSeeOther(django.core.urlresolvers.reverse("samples.views.main.main_menu"))
    else:
        sample_series_form = SampleSeriesForm(user_details, None)
    return render_to_response("edit_sample_series.html",
                              {"title": _(u"Create new sample series"),
                               "sample_series": sample_series_form,
                               "is_new": True,
                               "name_prefix": u"%02d-%s" % (datetime.datetime.today().year % 100, request.user.username)},
                              context_instance=RequestContext(request))


@login_required
def add_result_process(request, name):
    u"""View for appending a result process to a sample series.  For the rules
    of adding result processes, see `utils.get_allowed_result_processes`.

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
    user_details = utils.get_profile(request.user)
    processes = utils.get_allowed_result_processes(request.user, sample_series=[sample_series])
    if not processes:
        return utils.HttpResponseSeeOther("permission_error")
    return render_to_response("add_process.html",
                              {"title": _(u"Add result to “%s”") % name,
                               "processes": processes,
                               "query_string": "sample_series=%s&next=%s" % (urlquote_plus(name),
                                                                             sample_series.get_absolute_url())},
                              context_instance=RequestContext(request))
