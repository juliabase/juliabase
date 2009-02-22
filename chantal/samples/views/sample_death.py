#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View for killing a sample.
"""

from __future__ import absolute_import

import datetime
from django.shortcuts import render_to_response
from django.http import Http404
from django.template import RequestContext
from django.forms.util import ValidationError
from django import forms
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.decorators import login_required
from samples import models, permissions
from samples.views import utils


class SampleDeathForm(forms.ModelForm):
    u"""Model form for a sample death.  I only use the ``reason`` field here.
    Note that it is not possible to select a sample (or even more than a
    sample) here because the sample is already determinded by the URL of the
    request.
    """
    _ = ugettext_lazy
    def __init__(self, sample, *args, **kwargs):
        super(SampleDeathForm, self).__init__(*args, **kwargs)
        self.sample = sample
        if not sample.last_process_if_split():
            new_choices = []
            for choice in self.fields["reason"].choices:
                if choice[0] != "split":
                    new_choices.append(choice)
            self.fields["reason"].choices = new_choices
    def clean_reason(self):
        u"""Assure that if a sample was completely split, the most recent
        process was indeed a split.
        """
        reason = self.cleaned_data["reason"]
        if reason == "split" and not self.sample.last_process_if_split():
            raise ValidationError(_("Last process wasn't a split."))
        return reason
    class Meta:
        model = models.SampleDeath
        fields = ("reason",)


@login_required
def new(request, sample_name):
    u"""View for killing samples.  Note that it is not possible to re-kill an
    already dead sample.  Furthermore, you must be the currently responsible
    person to be able to kill a sample.

    :Parameters:
      - `request`: the current HTTP Request object
      - `sample_name`: name of the sample to be killed

    :type request: ``HttpRequest``
    :type sample_name: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    sample = utils.lookup_sample(sample_name, request)
    permissions.assert_can_edit_sample(request.user, sample)
    if sample.is_dead():
        raise Http404(u"Sample is already dead.")
    if request.method == "POST":
        sample_death_form = SampleDeathForm(sample, request.POST)
        if sample_death_form.is_valid():
            sample_death = sample_death_form.save(commit=False)
            sample_death.timestamp = datetime.datetime.now()
            sample_death.operator = request.user
            sample_death.save()
            sample_death.samples = [sample]
            # FixMe: Feed entries
            return utils.successful_response(request, _(u"Sample “%s” was killed.") % sample,
                                             "show_sample_by_name", {"sample_name": sample_name})
    else:
        sample_death_form = SampleDeathForm(sample)
    return render_to_response("edit_sample_death.html", {"title": _(u"Kill sample “%s”") % sample,
                                                         "sample_death": sample_death_form},
                              context_instance=RequestContext(request))
