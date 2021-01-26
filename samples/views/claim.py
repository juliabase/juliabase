# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""View function for claims to samples.  This means that users can ask other
priviledged users to become the currently responsible person of a sample or a
set of samples.
"""

import django.contrib.auth.models
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
import django.forms as forms
from django.forms.utils import ValidationError
from django.contrib.auth.decorators import login_required
import django.urls
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _, ugettext
from django.conf import settings
from jb_common.utils.base import help_link, send_email, get_really_full_name
import samples.utils.views as utils
from samples import permissions, models


class SamplesForm(forms.Form):
    samples = utils.MultipleSamplesField(label=_("Claimed samples"), help_text=_("“My Samples” are eligible."))

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["samples"].set_samples(user,
            user.my_samples.exclude(currently_responsible_person=user).
            filter(Q(topic__confidential=False) | Q(topic__members=user)).distinct())


class ReviewerChoiceField(forms.ModelChoiceField):
    """Custom field class just to have pretty-printed names in the reviewer
    selection.
    """
    def label_from_instance(self, user):
        return get_really_full_name(user)


class ReviewerForm(forms.Form):
    """Form giving the user who should approve the claim.
    """
    reviewer = ReviewerChoiceField(label=_("Requested reviewer"), queryset=None)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        permission = django.contrib.auth.models.Permission.objects.get(
            codename="adopt_samples", content_type=ContentType.objects.get_for_model(models.Sample))
        self.fields["reviewer"].queryset = django.contrib.auth.models.User.objects.filter(
            Q(groups__permissions=permission) | Q(user_permissions=permission)).distinct(). \
            order_by("last_name", "first_name")


@help_link("demo.html#the-actual-claim")
@login_required
def add(request, username):
    """View for adding a new claim.  The ``username`` parameter is actually
    superfluous because it must be the currently logged-in user anyway.  But
    this way, we don't get into trouble if a user happens to be called
    ``"add"``.  Additionally, the URLs become RESTful.

    :param request: the current HTTP Request object
    :param username: the name of the user whose claim this will be; it must be
        the currently logged-in user

    :type request: HttpRequest
    :type username: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    _ = ugettext
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if user != request.user:
        raise permissions.PermissionError(request.user, _("You are not allowed to add a claim in another user's name."))
    if request.method == "POST":
        samples_form = SamplesForm(user, request.POST)
        reviewer_form = ReviewerForm(request.POST)
        if samples_form.is_valid() and reviewer_form.is_valid():
            reviewer = reviewer_form.cleaned_data["reviewer"]
            claim = models.SampleClaim(requester=user, reviewer=reviewer)
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
                 "url": request.build_absolute_uri(django.urls.reverse("samples:show_claim", kwargs={"claim_id": claim.pk}))})
            _ = ugettext
            claim.samples.set(samples_form.cleaned_data["samples"])
            return utils.successful_response(request,
                                             _("Sample claim {id_} was successfully submitted.").format(id_=claim.pk),
                                             "samples:show_claim", kwargs={"claim_id": claim.pk})
    else:
        samples_form = SamplesForm(user)
        reviewer_form = ReviewerForm()
    return render(request, "samples/add_claim.html", {"title": _("Assert claim"), "samples": samples_form,
                                                      "reviewer": reviewer_form})



@help_link("demo.html#claims-of-samples")
@login_required
def list_(request, username):
    """View for listing claim, both those with you being the requester and the
    reviewer.  The ``username`` parameter is actually superfluous because it
    must be the currently logged-in user anyway.  But this way, it is more
    consistent and more RESTful.

    :param request: the current HTTP Request object
    :param username: the name of the user whose claims will be listed; it must
        be the currently logged-in user

    :type request: HttpRequest
    :type username: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    user = get_object_or_404(django.contrib.auth.models.User, username=username)
    if user != request.user and not user.is_superuser:
        raise permissions.PermissionError(request.user, _("You are not allowed to see claims of another user."))
    return render(request, "samples/list_claims.html",
                  {"title": _("Claims for {user}").format(user=get_really_full_name(user)),
                   "claims": user.claims.filter(closed=False),
                   "claims_as_reviewer": user.claims_as_reviewer.filter(closed=False)})


class CloseForm(forms.Form):
    close = forms.BooleanField(required=False)

    def __init__(self, label, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["close"].label = label


def is_referentially_valid(withdraw_form, approve_form):
    """Test whether all forms are consistent with each other.  I only test
    here whether the user has selected both checkboxes.  This can only happen
    if requester and reviewer are the same person (i.e., the user wants to aopt
    the samples himself).

    :return:
      whether all forms are consistent with each other

    :rtype: bool
    """
    referencially_valid = True
    if (approve_form and approve_form.cleaned_data["close"]) and \
            (withdraw_form and withdraw_form.cleaned_data["close"]):
        withdraw_form.add_error(None, ValidationError(_("You can't withdraw and approve at the same time."), code="invalid"))
        referencially_valid = False
    if (not approve_form or not approve_form.cleaned_data["close"]) and \
            (not withdraw_form or not withdraw_form.cleaned_data["close"]):
        withdraw_form.add_error(None, ValidationError(_("You must select exactly one option, or leave this page."),
                                                      code="invalid"))
        referencially_valid = False
    return referencially_valid


@login_required
def show(request, claim_id):
    """View for reviewing a claim.

    :param request: the current HTTP Request object
    :param claim_id: the primary key of the claim to be viewed

    :type request: HttpRequest
    :type claim_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    _ = ugettext
    claim = get_object_or_404(models.SampleClaim, pk=utils.convert_id_to_int(claim_id))
    is_reviewer = request.user == claim.reviewer or request.user.is_superuser
    is_requester = request.user == claim.requester
    if not is_reviewer and not is_requester:
        raise permissions.PermissionError(request.user, _("You are neither the requester nor the reviewer of this claim."))
    if request.method == "POST" and not claim.closed:
        withdraw_form = CloseForm(_("withdraw claim"), request.POST, prefix="withdraw") if is_requester else None
        approve_form = CloseForm(_("approve claim"), request.POST, prefix="approve") if is_reviewer else None
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
                sample_enumeration = "    " + ",\n    ".join(str(sample) for sample in sample_list)
                _ = lambda x: x
                send_email(_("Sample request approved"),
                       _("""Hello {requester},

your sample claim was approved.  You are now the “currently
responsible person” of the following samples:

{samples}

JuliaBase.
"""), claim.requester, {"requester": get_really_full_name(claim.requester), "samples": sample_enumeration})
                _ = ugettext
                response = \
                    utils.successful_response(request,
                                              _("Sample claim {id_} was successfully approved.").format(id_=claim.pk))
            if closed:
                claim.closed = True
                claim.save()
                response = response or \
                    utils.successful_response(request,
                                              _("Sample claim {id_} was successfully withdrawn.").format(id_=claim.pk))
            return response
    else:
        withdraw_form = CloseForm(_("withdraw claim"), prefix="withdraw") if is_requester else None
        approve_form = CloseForm(_("approve claim"), prefix="approve") if is_reviewer else None
    return render(request, "samples/show_claim.html", {"title": _("Claim #{number}").format(number=claim_id),
                                                       "claim": claim, "is_reviewer": is_reviewer,
                                                       "is_requester": is_requester,
                                                       "withdraw": withdraw_form, "approve": approve_form})


_ = ugettext
