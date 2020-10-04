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

"""The view for merging samples together.
"""

from django.utils.translation import ugettext_lazy as _, ugettext
from django.utils.text import capfirst
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.forms.utils import ValidationError
from django.urls import get_callable
from samples import models
import samples.utils.views as utils


class MergeSamplesForm(forms.Form):
    """The merge samples form class.
    """
    from_sample = utils.SampleField(label=_("merge sample"), required=False)
    to_sample = utils.SampleField(label=_("into sample"), required=False)

    def __init__(self, user, *args, **kwargs):
        """You may pass a ``choices`` keyword argument.  If given, it is used to
        initialize the choices of both fields instead of calling their
        :py:meth:`set_samples` methods.  This makes the constructor
        *drastically* faster.
        """
        choices = kwargs.pop("choices", None)
        super().__init__(*args, **kwargs)
        self.user = user
        if choices is None:
            self.fields["from_sample"].set_samples(user)
            choices = self.fields["from_sample"].choices
        else:
            self.fields["from_sample"].choices = choices
        self.fields["to_sample"].choices = choices

    def clean_from_sample(self):
        from_sample = self.cleaned_data["from_sample"]
        if from_sample and (from_sample.split_origin or models.SampleSplit.objects.filter(parent=from_sample).exists()
                            or models.SampleDeath.objects.filter(samples=from_sample).exists()):
            raise ValidationError(
                _("It is not possible to merge a sample that was split, killed, or is the result of a sample split."),
                code="invalid")
        return from_sample

    def clean(self):
        def get_first_process(sample, process_cls):
            try:
                return process_cls.objects.filter(samples=sample)[0]
            except IndexError:
                return None

        cleaned_data = super().clean()
        from_sample = cleaned_data.get("from_sample")
        to_sample = cleaned_data.get("to_sample")
        if from_sample and not to_sample:
            self.add_error(None, ValidationError(_("You must select a target sample."), code="required"))
        elif not from_sample and to_sample:
            self.add_error(None, ValidationError(_("You must select a source sample."), code="required"))
        elif from_sample and to_sample:
            if not (from_sample.currently_responsible_person == to_sample.currently_responsible_person == self.user) \
                    and not self.user.is_superuser:
                self.add_error(None, ValidationError(_("You must be the currently responsible person of both samples."),
                                                     code="forbidden"))
                cleaned_data.pop(from_sample, None)
                cleaned_data.pop(to_sample, None)
            if from_sample == to_sample:
                self.add_error(None, ValidationError(_("You can't merge a sample into itself."), code="invalid"))
                cleaned_data.pop(from_sample, None)
                cleaned_data.pop(to_sample, None)
            sample_death = get_first_process(to_sample, models.SampleDeath)
            sample_split = get_first_process(to_sample, models.SampleSplit)
            if sample_death or sample_split:
                try:
                    latest_process = from_sample.processes.all().reverse()[0]
                except IndexError:
                    pass
                else:
                    if sample_death and sample_death.timestamp <= latest_process.timestamp:
                        self.add_error(None, ValidationError(
                            _("One or more processes would be after sample death of %(to_sample)s."),
                            params={"to_sample": to_sample.name}, code="invalid"))
                        cleaned_data.pop(from_sample, None)
                    if sample_split and sample_split.timestamp <= latest_process.timestamp:
                        self.add_error(None, ValidationError(
                            _("One or more processes would be after sample split of %(to_sample)s."),
                            params={"to_sample": to_sample.name}, code="invalid"))
                        cleaned_data.pop(from_sample, None)
        return cleaned_data


def merge_samples(from_sample, to_sample):
    """Copies all processes from one sample to another sample.
    The fist sample will be erased afterwards.

    :param from_sample: The sample, who is merged into the other sample
    :param to_sample: The sample, who should contains the processes from the
        other sample

    :type from_sample: `samples.models.Sample`
    :type to_sample: `samples.models.Sample`
    """
    current_sample = to_sample
    for process in from_sample.processes.order_by("-timestamp"):
        if current_sample.split_origin and current_sample.split_origin.timestamp > process.timestamp:
            current_sample = current_sample.split_origin.parent
        current_sample.processes.add(process)
    to_sample.series.add(*from_sample.series.all())
    to_aliases = {alias.name for alias in to_sample.aliases.all()}
    to_sample.aliases.add(*(alias for alias in from_sample.aliases.all() if alias.name not in to_aliases))
    if not to_sample.aliases.filter(name=from_sample.name).exists():
        to_sample.aliases.create(name=from_sample.name)
    if settings.MERGE_CLEANUP_FUNCTION:
        cleanup_after_merge = get_callable(settings.MERGE_CLEANUP_FUNCTION)
        cleanup_after_merge(from_sample, to_sample)
    from_sample.delete()


def is_referentially_valid(merge_samples_forms):
    """Test whether all forms are consistent with each other.

    :param merge_samples_forms: all “merge samples forms”

    :type new_name_forms: list of `MergeSamplesForm`

    :return:
      whether all forms are consistent with each other

    :rtype: bool
    """
    referentially_valid = True
    from_samples = set()
    to_samples = set()
    for merge_samples_form in merge_samples_forms:
        if merge_samples_form.is_valid():
            from_sample = merge_samples_form.cleaned_data["from_sample"]
            to_sample = merge_samples_form.cleaned_data["to_sample"]
            if from_sample in from_samples or to_sample in from_samples:
                merge_samples_form.add_error(None, ValidationError(_("You can merge a sample only once."), code="invalid"))
                referentially_valid = False
            if from_sample in to_samples:
                merge_samples_form.add_error(None, ValidationError(
                    _("You can't merge a sample which was merged shortly before.  Do this in a separate call."),
                    code="invalid"))
                referentially_valid = False
            if from_sample:
                from_samples.add(from_sample)
            if to_sample:
                to_samples.add(to_sample)
    if referentially_valid and all(merge_samples_form.is_valid() for merge_samples_form in merge_samples_forms) \
            and not from_samples:
        merge_samples_forms[0].add_error(None, ValidationError(_("No samples selected."), code="required"))
        referentially_valid = False
    return referentially_valid


number_of_pairs = 6

@login_required
def merge(request):
    """The merging of the samples is handled in this function.
    It creates the necessary forms, initiates the merging
    and returns the HttpResponse to the web browser.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    def build_merge_forms(data=None):
        merge_samples_forms = [MergeSamplesForm(request.user, data, prefix=str(0))]
        choices = merge_samples_forms[0].fields["from_sample"].choices
        merge_samples_forms += [MergeSamplesForm(request.user, data, prefix=str(index), choices=choices)
                                for index in range(1, number_of_pairs)]
        return merge_samples_forms
    if request.method == "POST":
        merge_samples_forms = build_merge_forms(request.POST)
        all_valid = all([merge_samples_form.is_valid() for merge_samples_form in merge_samples_forms])
        referentially_valid = is_referentially_valid(merge_samples_forms)
        if all_valid and referentially_valid:
            for merge_samples_form in merge_samples_forms:
                from_sample = merge_samples_form.cleaned_data.get("from_sample")
                to_sample = merge_samples_form.cleaned_data.get("to_sample")
                if from_sample and to_sample:
                    merge_samples(from_sample, to_sample)
            return utils.successful_response(request, _("Samples were successfully merged."))
    else:
        merge_samples_forms = build_merge_forms()
    return render(request, "samples/merge_samples.html", {"title": capfirst(_("merge samples")),
                                                          "merge_forms": merge_samples_forms})


_ = ugettext
