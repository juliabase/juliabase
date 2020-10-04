# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


"""View function for claims to samples.  This complements the claim views of
JuliaBase-samples.  The additional feature is that one can claim samples with
old-style names which do not exist in the database yet.
"""

import django.contrib.auth.models
from django.shortcuts import render, get_object_or_404
import django.forms as forms
from django.forms.utils import ValidationError
from django.contrib.auth.decorators import login_required
import django.urls
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
import django.utils.timezone
from django.conf import settings
from jb_common.utils.base import help_link, send_email, get_really_full_name, format_enumeration
from jb_common.models import Topic
import samples.utils.views as utils
from samples.utils import sample_names
from samples import permissions
from samples.models import Sample, SampleClaim
from samples.views.claim import ReviewerForm
from institute import models


# FixMe: This module contains a lot of code duplication from
# ``samples.views.claim``, which is not bad in itself (for this, it's too
# little), but many translations are doubled.


class SamplesForm(forms.Form):
    samples = forms.CharField(label=_("Samples"), help_text=_("Comma-separated"), widget=forms.widgets.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["samples"].widget.attrs.update({"cols": 30, "rows": 5})

    def clean_samples(self):
        sample_names = self.cleaned_data["samples"].split(",")
        valid_names = []
        invalid_names = []
        for name in sample_names:
            name = name.strip()
            if name:
                if sample_names.sample_name_format(name) == "old":
                    if name in valid_names:
                        raise ValidationError(_("The name %(name)s appears more than once."), params={"name": name},
                                              code="invalid")
                    valid_names.append(name)
                else:
                    invalid_names.append(name)
        if invalid_names:
            error_message = ungettext(
                "The name %(invalid_names)s is not valid.", "The names %(invalid_names)s are not valid.",
                len(invalid_names))
            raise ValidationError(error_message, params={"invalid_names": format_enumeration(invalid_names)}, code="invalid")
        if not valid_names:
            raise ValidationError(self.fields["samples"].error_messages["required"], code="required")
        existing_names = [name for name in valid_names if sample_names.does_sample_exist(name)]
        if existing_names:
            # This opens a small security hole because people can find out that
            # confidential samples are existing.  However, such samples mostly
            # have non-oldstyle names anyway.
            error_message = ungettext(
                "The name %(existing_names)s is already existing.", "The names %(existing_names)s are already existing.",
                len(existing_names))
            raise ValidationError(error_message, params={"existing_names": format_enumeration(existing_names)},
                                  code="duplicate")
        return valid_names


class SubstrateForm(forms.ModelForm):

    class Meta:
        model = models.Substrate
        fields = ("material", "comments")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comments"].widget.attrs.update({"cols": 30, "rows": 5})

    def clean(self):
        cleaned_data = super().clean()
        if "material" in cleaned_data and "comments" in cleaned_data:
            if cleaned_data["material"] == "custom" and not cleaned_data["comments"]:
                self.add_error("comments", ValidationError(_("For a custom substrate, you must give substrate comments."),
                                                           code="invalid"))
        return cleaned_data


@help_link("demo.html#the-actual-claim")
@login_required
def add_oldstyle(request, username):
    """View for adding a new claim to old-style sample names.  This is a nice
    example of a view of the app “samples” which is *extended* in the institute
    app.  The template – in this case,
    :file:`institute/templates/samples/list_claims.html` – overrides and extends the
    default one, and adds a link to a URL listed in institute's URLconf and pointing
    to this view function.

    The important step is the template.  This is the hook for your extensions.
    You override the template from “samples” by creating a file called the same
    in :file:`institute/templates/samples/`.  Because ``DIRS`` and ``loaders``
    are defined as recommended in :doc:`/programming/settings`, it shadows its
    counterpart.  By giving the full path, you can still access the original.
    Thus, you may start your template with

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
                 "url": request.build_absolute_uri(django.urls.reverse("samples:show_claim", kwargs={"claim_id": claim.pk}))})
            _ = ugettext
            samples = []
            nobody = django.contrib.auth.models.User.objects.get(username="nobody")
            legacy = Topic.objects.get(name="Legacy")
            now = django.utils.timezone.now()
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
                                             "samples:show_claim", kwargs={"claim_id": claim.pk})
    else:
        samples_form = SamplesForm()
        substrate_form = SubstrateForm()
        reviewer_form = ReviewerForm()
    return render(request, "samples/add_claim_oldstyle.html", {"title": _("Assert claim"), "samples": samples_form,
                                                               "substrate": substrate_form, "reviewer": reviewer_form})


_ = ugettext
