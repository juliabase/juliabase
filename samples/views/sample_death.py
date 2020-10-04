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


"""View for killing a sample.
"""

from django.shortcuts import render
from django.http import Http404
from django.forms.utils import ValidationError
from django import forms
import django.utils.timezone
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.auth.decorators import login_required
from jb_common.utils.base import unquote_view_parameters
from samples import models, permissions
import samples.utils.views as utils


class SampleDeathForm(forms.ModelForm):
    """Model form for a sample death.  I only use the ``reason`` field here.
    Note that it is not possible to select a sample (or even more than a
    sample) here because the sample is already determinded by the URL of the
    request.
    """
    class Meta:
        model = models.SampleDeath
        fields = ("reason",)

    def __init__(self, sample, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sample = sample
        if not sample.last_process_if_split():
            new_choices = []
            for choice in self.fields["reason"].choices:
                if choice[0] != "split":
                    new_choices.append(choice)
            self.fields["reason"].choices = new_choices

    def clean_reason(self):
        """Assure that if a sample was completely split, the most recent
        process was indeed a split.
        """
        reason = self.cleaned_data["reason"]
        if reason == "split" and not self.sample.last_process_if_split():
            raise ValidationError(_("Last process wasn't a split."), code="invalid")
        return reason


@login_required
@unquote_view_parameters
def new(request, sample_name):
    """View for killing samples.  Note that it is not possible to re-kill an
    already dead sample.  Furthermore, you must be the currently responsible
    person to be able to kill a sample.

    :param request: the current HTTP Request object
    :param sample_name: name of the sample to be killed

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    permissions.assert_can_edit_sample(request.user, sample)
    if sample.is_dead():
        raise Http404("Sample is already dead.")
    if request.method == "POST":
        sample_death_form = SampleDeathForm(sample, request.POST)
        if sample_death_form.is_valid():
            sample_death = sample_death_form.save(commit=False)
            sample_death.timestamp = django.utils.timezone.now()
            sample_death.operator = request.user
            sample_death.save()
            sample_death_form.save_m2m()
            sample_death.samples.set([sample])
            # FixMe: Feed entries
            return utils.successful_response(request, _("Sample “{sample}” was killed.").format(sample=sample),
                                             "samples:show_sample_by_name", {"sample_name": sample_name})
    else:
        sample_death_form = SampleDeathForm(sample)
    return render(request, "samples/edit_sample_death.html", {"title": _("Kill sample “{sample}”").format(sample=sample),
                                                              "sample_death": sample_death_form})


_ = ugettext
