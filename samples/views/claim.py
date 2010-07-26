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
from django.core.mail import send_mail
from samples import models, permissions
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import urlquote_plus
import django.core.urlresolvers
from django.utils.translation import ugettext as _, ugettext_lazy, ungettext
from django.conf import settings
from chantal_common.utils import append_error, HttpResponseSeeOther, adjust_timezone_information
from samples.views import utils, form_utils, feed_utils, csv_export
from samples import permissions, models
from chantal_common.utils import get_really_full_name


class SamplesForm(forms.Form):
    _ = ugettext_lazy
    samples = form_utils.MultipleSamplesField(label=_(u"Claimed samples"), help_text=_(u"“My Samples” are eligible."))

    def __init__(self, user, *args, **kwargs):
        super(SamplesForm, self).__init__(*args, **kwargs)
        self.fields["samples"].set_samples(user.my_samples.all(), user)


class ApproverForm(forms.Form):
    u"""Form giving the user who should approve the claim.
    """
    _ = ugettext_lazy
    approver = forms.ModelChoiceField(label=_(u"Requested approver"), queryset=None)
    def __init__(self, *args, **kwargs):
        super(ApproverForm, self).__init__(*args, **kwargs)
        permission = django.contrib.auth.models.Permission.objects.get(codename="adopt_samples")
        self.fields["approver"].queryset = django.contrib.auth.models.User.objects.filter(
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
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if user != request.user:
        raise permissions.PermissionError(request.user, _(u"You are not allowed to add a claim in another user's name."))
    if request.method == "POST":
        samples_form = SamplesForm(user, request.POST)
        approver_form = ApproverForm(request.POST)
        if samples_form.is_valid() and approver_form.is_valid():
            approver = approver_form.cleaned_data["approver"]
            claim = models.Claim(requester=user, approver=approver)
            claim.save()
            claim.samples = samples=samples_form.cleaned_data["samples"]
            send_mail(_("Sample request from {requester}").format(requester=get_really_full_name(user)),
                      _(u"""Hello {approver},

{requester} wants to become the new “currently responsible person”
of one or more samples.  Please visit

    {url}

for reviewing this request.  If you don't want or cannot approve
the request, please contact {requester} directly and ask him or her
to withdraw the request.

Chantal.
""").format(approver=get_really_full_name(approver), requester=get_really_full_name(user),
            url="http://" + settings.DOMAIN_NAME + django.core.urlresolvers.reverse(view, kwargs={"claim_id": claim.pk})),
                      settings.DEFAULT_FROM_EMAIL, [approver.email], fail_silently=False)
            return utils.successful_response(request, _(u"Claim {id_} was successfully asserted.").format(id_=claim.pk),
                                             view, kwargs={"claim_id": claim.pk})
    else:
        samples_form = SamplesForm(user)
        approver_form = ApproverForm()
    return render_to_response("samples/add_claim.html", {"title": _(u"Assert claim"), "samples": samples_form,
                                                         "approver": approver_form},
                              context_instance=RequestContext(request))



@login_required
def list_(request, username):
    pass


@login_required
def view(request, claim_id):
    pass
