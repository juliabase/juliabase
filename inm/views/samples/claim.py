#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""View function for claims to samples.  This complements the claim views of
JuliaBase-samples.  The additional feature is that one can claim samples with
old-style names which do not exist in the database yet.
"""

from __future__ import absolute_import, unicode_literals

import datetime
import django.contrib.auth.models
from django.shortcuts import render, get_object_or_404
import django.forms as forms
from django.forms.util import ValidationError
from django.contrib.auth.decorators import login_required
import django.core.urlresolvers
from django.utils.translation import ugettext, ugettext_lazy, ungettext
from django.conf import settings
from jb_common.utils import send_email, get_really_full_name, format_enumeration
from jb_common.models import Topic
from samples.views import utils
from samples import permissions
from samples.models import Sample, SampleClaim
from inm import models
from samples.views.claim import ReviewerForm


# FixMe: This module contains a lot of code duplication from
# ``samples.views.claim``, which is not bad in itself (for this, it's too
# little), but many translations are doubled.


class SamplesForm(forms.Form):
    _ = ugettext_lazy
    samples = forms.CharField(label=_("Samples"), help_text=_("Comma-separated"), widget=forms.widgets.Textarea)

    def __init__(self, *args, **kwargs):
        super(SamplesForm, self).__init__(*args, **kwargs)
        self.fields["samples"].widget.attrs.update({"cols": 30, "rows": 5})

    def clean_samples(self):
        _ = ugettext
        sample_names = self.cleaned_data["samples"].split(",")
        valid_names = []
        invalid_names = []
        for name in sample_names:
            name = name.strip()
            if name:
                if utils.sample_name_format(name) == "old":
                    if name in valid_names:
                        raise ValidationError(_("The name {name} appears more than once.").format(name=name))
                    valid_names.append(name)
                else:
                    invalid_names.append(name)
        if invalid_names:
            error_message = ungettext(
                "The name {invalid_names} is not valid.", "The names {invalid_names} are not valid.",
                len(invalid_names)).format(invalid_names=format_enumeration(invalid_names))
            raise ValidationError(error_message)
        if not valid_names:
            raise ValidationError(self.fields["samples"].error_messages["required"])
        existing_names = [name for name in valid_names if utils.does_sample_exist(name)]
        if existing_names:
            # This opens a small security hole because people can find out that
            # confidential samples are existing.  However, such samples mostly
            # have non-oldstyle names anyway.
            error_message = ungettext(
                "The name {existing_names} is already existing.", "The names {existing_names} are already existing.",
                len(existing_names)).format(existing_names=format_enumeration(existing_names))
            raise ValidationError(error_message)
        return valid_names


class SubstrateForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(SubstrateForm, self).__init__(*args, **kwargs)
        self.fields["comments"].widget.attrs.update({"cols": 30, "rows": 5})

    def clean(self):
        _ = ugettext
        cleaned_data = self.cleaned_data
        if "material" in cleaned_data and "comments" in cleaned_data:
            if cleaned_data["material"] == "custom" and not cleaned_data["comments"]:
                self.add_error("comments", _("For a custom substrate, you must give substrate comments."))
        return cleaned_data

    class Meta:
        model = models.Substrate
        fields = ("material", "comments")


@login_required
def add_oldstyle(request, username):
    """View for adding a new claim to old-style sample names.  This is a nice
    example of a view of the app “samples” which is *extended* in the institute
    app.  The template – in this case,
    :file:`inm/templates/samples/list_claims.html` – overrides and extends the
    default one, and adds a link to a URL listed in inm's URLconf and pointing
    to this view function.

    The important step is the template.  This is the hook for your extensions.
    You override the template from “samples” by creating a file called the same
    in :file:`inm/templates/samples/`.  Because ``TEMPLATE_DIRS`` and
    ``TEMPLATE_LOADERS`` are defined as recommended in
    :doc:`/programming/settings`, it shadows its counterpart.  By giving the
    full path, you can still access the original.  Thus, you may start your
    template with

    ::

        {% extends "samples/templates/samples/list_claims.html" %}

    in order to extend it.

    The `username` parameter of this view function is actually superfluous
    because it must be the currently logged-in user anyway.  But this way, we
    don't get into trouble if a user happens to be called ``"add"``.
    Additionally, the URLs become RESTful.

    :param request: the current HTTP Request object
    :param username: the name of the user whose claim this will be; it must be
        the currently logged-in user

    :type request: HttpRequest
    :type username: unicode

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    _ = ugettext
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if user != request.user:
        raise permissions.PermissionError(request.user, _("You are not allowed to add a claim in another user's name."))
    if request.method == "POST":
        samples_form = SamplesForm(request.POST)
        substrate_form = SubstrateForm(request.POST)
        reviewer_form = ReviewerForm(request.POST)
        if samples_form.is_valid() and substrate_form.is_valid() and reviewer_form.is_valid():
            reviewer = reviewer_form.cleaned_data["reviewer"]
            claim = SampleClaim(requester=user, reviewer=reviewer)
            claim.save()
            _ = lambda x: x
            send_email(_("Sample request from {requester}"),
                       _("""Hello {reviewer},

{requester} wants to become the new “currently responsible person”
of one or more samples.  Please visit

    {url}

for reviewing this request.  If you don't want or cannot approve
the request, please contact {requester} directly and ask him or her
to withdraw the request.

JuliaBase.
"""), reviewer, {"reviewer": get_really_full_name(reviewer), "requester": get_really_full_name(user),
                 "url": request.build_absolute_uri(django.core.urlresolvers.reverse("samples.views.claim.show",
                                                                                    kwargs={"claim_id": claim.pk}))})
            _ = ugettext
            samples = []
            nobody = django.contrib.auth.models.User.objects.get(username="nobody")
            legacy = Topic.objects.get(name="Legacy")
            now = datetime.datetime.now()
            material, substrate_comments = substrate_form.cleaned_data["material"], substrate_form.cleaned_data["comments"]
            for name in samples_form.cleaned_data["samples"]:
                substrate = models.Substrate(operator=nobody, timestamp=now, material=material, comments=substrate_comments)
                substrate.save()
                sample = Sample(name=name, current_location="unknown", currently_responsible_person=nobody, topic=legacy)
                sample.save()
                sample.processes.add(substrate)
                samples.append(sample)
            claim.samples = samples
            return utils.successful_response(request,
                                             _("Sample claim {id_} was successfully submitted.").format(id_=claim.pk),
                                             "samples.views.claim.show", kwargs={"claim_id": claim.pk})
    else:
        samples_form = SamplesForm()
        substrate_form = SubstrateForm()
        reviewer_form = ReviewerForm()
    return render(request, "samples/add_claim_oldstyle.html", {"title": _("Assert claim"), "samples": samples_form,
                                                               "substrate": substrate_form, "reviewer": reviewer_form})
