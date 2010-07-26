#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View function for claims to samples.  This means that users can ask other
priviledged users to become the currently responsible person of a sample or a
set of samples.
"""

from __future__ import absolute_import

import time, copy, hashlib
from django.views.decorators.http import condition
import django.contrib.auth.models
from django.db.models import Q
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
import django.forms as forms
from django.core.cache import cache
from samples import models, permissions
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import urlquote_plus
import django.core.urlresolvers
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy, ungettext
from django.conf import settings
from chantal_common.utils import append_error, HttpResponseSeeOther, adjust_timezone_information, send_email
from samples.views import utils, form_utils, feed_utils, csv_export
from samples import permissions, models
from chantal_common.utils import get_really_full_name


class SamplesForm(forms.Form):
    _ = ugettext_lazy
    samples = form_utils.MultipleSamplesField(label=_(u"Claimed samples"), help_text=_(u"“My Samples” are eligible."))

    def __init__(self, user, *args, **kwargs):
        super(SamplesForm, self).__init__(*args, **kwargs)
        self.fields["samples"].set_samples(user.my_samples.all(), user)


class ReviewerForm(forms.Form):
    u"""Form giving the user who should approve the claim.
    """
    _ = ugettext_lazy
    reviewer = forms.ModelChoiceField(label=_(u"Requested reviewer"), queryset=None)
    def __init__(self, *args, **kwargs):
        super(ReviewerForm, self).__init__(*args, **kwargs)
        permission = django.contrib.auth.models.Permission.objects.get(codename="adopt_samples")
        self.fields["reviewer"].queryset = django.contrib.auth.models.User.objects.filter(
            Q(groups__permissions=permission) | Q(user_permissions=permission)).distinct()


@login_required
def add(request, username):
    u"""View for adding a new claim.  The ``username`` parameter is actually
    superfluous because it must be the currently logged-in user anyway.  But
    this way, we don't get into trouble if a user happens to be called
    ``"add"``.  Additionally, the URLs become RESTful.

    :Parameters:
      - `request`: the current HTTP Request object
      - `username`: the name of the user whose claim this will be; it must be
        the currently logged-in user

    :type request: ``HttpRequest``
    :type username: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    _ = ugettext
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if user != request.user:
        raise permissions.PermissionError(request.user, _(u"You are not allowed to add a claim in another user's name."))
    if request.method == "POST":
        samples_form = SamplesForm(user, request.POST)
        reviewer_form = ReviewerForm(request.POST)
        if samples_form.is_valid() and reviewer_form.is_valid():
            reviewer = reviewer_form.cleaned_data["reviewer"]
            claim = models.SampleClaim(requester=user, reviewer=reviewer)
            claim.save()
            _ = lambda x: x
            send_email(_("Sample request from {requester}"),
                       _(u"""Hello {reviewer},

{requester} wants to become the new “currently responsible person”
of one or more samples.  Please visit

    {url}

for reviewing this request.  If you don't want or cannot approve
the request, please contact {requester} directly and ask him or her
to withdraw the request.

Chantal.
"""), reviewer, {"reviewer": get_really_full_name(reviewer), "requester": get_really_full_name(user),
                 "url": "http://" + settings.DOMAIN_NAME +
                 django.core.urlresolvers.reverse(show, kwargs={"claim_id": claim.pk})})
            _ = ugettext
            claim.samples = samples=samples_form.cleaned_data["samples"]
            return utils.successful_response(request,
                                             _(u"Sample claim {id_} was successfully submitted.").format(id_=claim.pk),
                                             show, kwargs={"claim_id": claim.pk})
    else:
        samples_form = SamplesForm(user)
        reviewer_form = ReviewerForm()
    return render_to_response("samples/add_claim.html", {"title": _(u"Assert claim"), "samples": samples_form,
                                                         "reviewer": reviewer_form},
                              context_instance=RequestContext(request))



@login_required
def list_(request, username):
    pass


class CloseForm(forms.Form):
    _ = ugettext_lazy
    close = forms.BooleanField(required=False)

    def __init__(self, label, *args, **kwargs):
        super(CloseForm, self).__init__(*args, **kwargs)
        self.fields["close"].label = label


def is_referentially_valid(withdraw_form, approve_form):
    u"""Test whether all forms are consistent with each other.  I only test
    here whether the user has selected both checkboxes.  This can only happen
    if requester and reviewer are the same person (i.e., the user wants to aopt
    the samples himself).

    :Return:
      whether all forms are consistent with each other

    :rtype: bool
    """
    referencially_valid = True
    if (approve_form and approve_form.cleaned_data["close"]) and \
            (withdraw_form and withdraw_form.cleaned_data["close"]):
        append_error(withdraw_form, _(u"You can't withdraw and approve at the same time."))
        referencially_valid = False
    if (approve_form and not approve_form.cleaned_data["close"]) and \
            (withdraw_form and not withdraw_form.cleaned_data["close"]):
        append_error(withdraw_form, _(u"You must select exactly one option, or leave this page."))
        referencially_valid = False
    return referencially_valid


@login_required
def show(request, claim_id):
    u"""View for reviewing a claim.  

    :Parameters:
      - `request`: the current HTTP Request object
      - `claim_id`: the primary key of the claim to be viewd

    :type request: ``HttpRequest``
    :type claim_id: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    _ = ugettext
    claim = get_object_or_404(models.SampleClaim, pk=utils.int_or_zero(claim_id))
    is_reviewer = request.user == claim.reviewer
    is_requester = request.user == claim.requester
    if not is_reviewer and not is_requester:
        raise permissions.PermissionError(request.user, _(u"You are neither the requester nor the reviewer of this claim."))
    if request.method == "POST" and not claim.closed:
        withdraw_form = CloseForm(_(u"withdraw claim"), request.POST, prefix="withdraw") if is_requester else None
        approve_form = CloseForm(_(u"approve claim"), request.POST, prefix="approve") if is_reviewer else None
        all_valid = (withdraw_form is None or withdraw_form.is_valid()) and (approve_form is None or approve_form.is_valid())
        referencially_valid = is_referentially_valid(withdraw_form, approve_form)
        if all_valid and referencially_valid:
            approved = approve_form and approve_form.cleaned_data["close"]
            closed = approved or (withdraw_form and withdraw_form.cleaned_data["close"])
            response = None
            if approved:
                sample_list = list(claim.samples.all())
                for sample in sample_list:
                    sample.currently_responsible_person = claim.requester
                    sample.save()
                sample_enumeration = u"    " + u",\n    ".join(unicode(sample) for sample in sample_list)
                _ = lambda x: x
                send_email(_("Sample request approved"),
                       _(u"""Hello {requester},

your sample claim was approved.  You are now the “currently
responsible person” of the following samples:

{samples}

Chantal.
"""), claim.requester, {"requester": get_really_full_name(claim.requester), "samples": sample_enumeration})
                _ = ugettext
                response = \
                    utils.successful_response(request,
                                              _(u"Sample claim {id_} was successfully approved.").format(id_=claim.pk))
            if closed:
                claim.closed = True
                claim.save()
                response = response or \
                    utils.successful_response(request,
                                              _(u"Sample claim {id_} was successfully withdrawn.").format(id_=claim.pk))
            return response
    else:
        withdraw_form = CloseForm(_(u"withdraw claim"), prefix="withdraw") if is_requester else None
        approve_form = CloseForm(_(u"approve claim"), prefix="approve") if is_reviewer else None
    return render_to_response("samples/show_claim.html", {"title": _(u"Claim #{number}").format(number=claim_id),
                                                          "claim": claim, "is_reviewer": is_reviewer,
                                                          "is_requester": is_requester,
                                                          "withdraw": withdraw_form, "approve": approve_form},
                              context_instance=RequestContext(request))
