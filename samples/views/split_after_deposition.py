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


"""Here are the views for a split immediately after a deposition.  In contrast
to the actual split view, you see all samples of the deposition at once, and
you can rename and/or split them.
"""

import datetime
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.utils.text import capfirst
from django.contrib.auth.decorators import login_required
import django.contrib.auth.models
from django.forms import Form
from django import forms
from django.forms.utils import ValidationError
from django.contrib.contenttypes.models import ContentType
from jb_common.utils.base import is_json_requested, unquote_view_parameters, int_or_zero, format_enumeration
from samples import models, permissions
import samples.utils.views as utils
from samples.utils import sample_names


class OriginalDataForm(Form):
    """Form holding the old sample, the new name for the unsplit sample, and
    the number of pieces it is about to be split into.
    """
    sample = forms.CharField(label=capfirst(_("old sample name")), max_length=30,
                             widget=forms.TextInput(attrs={"readonly": "readonly", "style": "text-align: center"}))
    new_name = forms.CharField(label=_("New name"), max_length=30)
    number_of_pieces = forms.IntegerField(label=_("Pieces"), initial="1",
                                          widget=forms.TextInput(attrs={"size": "3", "style": "text-align: center"}))

    def __init__(self, remote_client, deposition_number, post_data=None, *args, **kwargs):
        if "initial" not in kwargs:
            kwargs["initial"] = {}
        super().__init__(post_data, *args, **kwargs)
        self.remote_client, self.deposition_number = remote_client, deposition_number

    def clean_new_name(self):
        if "sample" in self.cleaned_data:
            new_name = self.cleaned_data["new_name"]
            if new_name != self.cleaned_data["sample"].name and sample_names.does_sample_exist(new_name):
                raise ValidationError(_("This sample name exists already."), code="duplicate")
            elif sample_names.sample_name_format(new_name) == "provisional":
                raise ValidationError(_("You must get rid of the provisional sample name."), code="invalid")
            return new_name

    def clean_sample(self):
        if not self.remote_client:
            sample = sample_names.get_sample(self.cleaned_data["sample"])
            if sample is None:
                raise ValidationError(_("No sample with this name found."), code="invalid")
            if isinstance(sample, list):
                raise ValidationError(_("Alias is not unique."), code="duplicate")
        else:
            try:
                sample = models.Sample.objects.get(pk=int(self.cleaned_data["sample"]))
            except models.Sample.DoesNotExist:
                raise ValidationError(_("No sample with this ID found."), code="invalid")
            except ValueError:
                raise ValidationError(_("Invalid ID format."), code="invalid")
        return sample

    def clean_number_of_pieces(self):
        if self.cleaned_data["number_of_pieces"] <= 0:
            raise ValidationError(_("Must be at least 1."), code="invalid")
        return self.cleaned_data["number_of_pieces"]

    def clean(self):
        cleaned_data = super().clean()
        if "new_name" in cleaned_data:
            new_name = cleaned_data["new_name"]
            sample = cleaned_data.get("sample")
            if sample and sample_names.sample_name_format(sample.name) is not None and \
               not sample_names.valid_new_sample_name(sample.name, new_name) and \
               not new_name.startswith(sample.name):
                error_message = _("The new name must begin with the old name.")
                params = {}
                old_sample_name_format = sample_names.sample_name_format(sample.name)
                possible_new_name_formats = settings.SAMPLE_NAME_FORMATS[old_sample_name_format].get("possible_renames", set())
                if possible_new_name_formats:
                    error_message += ungettext("  Alternatively, it must be a valid “%(sample_formats)s” name.",
                                               "  Alternatively, it must be a valid name of one of these types: "
                                               "%(sample_formats)s.", len(possible_new_name_formats))
                    params.update({"sample_formats": format_enumeration(
                        sample_names.verbose_sample_name_format(name_format) for name_format in possible_new_name_formats)})
                if sample_names.valid_new_sample_name(sample.name, self.deposition_number):
                    error_message += _("  Or, the new name must be or begin with the deposition number.")
                self.add_error("new_name", ValidationError(error_message, params=params, code="invalid"))
        return cleaned_data


class NewNameForm(Form):
    """Form holding the newly given name of a sample.
    """
    new_name = forms.CharField(label=capfirst(_("new sample name")), max_length=30)

    def __init__(self, user, readonly, data=None, **kwargs):
        super().__init__(data, **kwargs)
        self.fields["new_name"].widget = forms.TextInput(attrs={"size": "15"})
        if readonly:
            self.fields["new_name"].widget.attrs["readonly"] = "readonly"
        self.user = user

    def clean_new_name(self):
        new_name = self.cleaned_data["new_name"]
        sample_name_format = sample_names.sample_name_format(new_name)
        if not sample_name_format:
            raise ValidationError(_("The sample name has an invalid format."), code="invalid")
        return new_name


class GlobalNewDataForm(Form):
    """Form for holding new data which applies to all samples and overrides
    local settings.
    """
    new_location = forms.CharField(label=_("New current location"), max_length=50, required=False,
                                   help_text=_("(for all samples; leave empty for no change)"))

    def __init__(self, data=None, **kwargs):
        """I have to initialise the field here, both their
        value and their layout.
        """
        deposition_instance = kwargs.pop("deposition_instance")
        super().__init__(data, **kwargs)
        self.fields["new_location"].initial = \
            models.default_location_of_deposited_samples.get(deposition_instance.__class__, "")
        self.fields["new_location"].widget = forms.TextInput(attrs={"size": "40"})


def is_all_valid(original_data_forms, new_name_form_lists, global_new_data_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :param original_data_forms: all old samples and pieces numbers
    :param new_name_form_lists: new names for all pieces
    :param global_new_data_form: the global, overriding settings

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of list of `NewNameForm`
    :type global_new_data_form: `GlobalNewDataForm`

    :return:
      whether all forms are valid according to their ``is_valid()`` method

    :rtype: bool
    """
    valid = all([original_data_form.is_valid() for original_data_form in original_data_forms])
    for forms in new_name_form_lists:
        valid = valid and all([new_name_form.is_valid() for new_name_form in forms])
    valid = valid and global_new_data_form.is_valid()
    return valid


def change_structure(user, original_data_forms, new_name_form_lists):
    """Add or delete new data form according to the new number of pieces
    entered by the user.  While changes in form fields are performs by the form
    objects themselves, they can't change the *structure* of the view.  This is
    performed here.

    :param user: the current user
    :param original_data_forms: all old samples and pieces numbers
    :param new_name_form_lists: new names for all pieces

    :type user: django.contrib.auth.models.User
    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of list of `NewNameForm`

    :return:
      whether the structure was changed, i.e. whether the number of pieces of
      one sample has been changed by the user

    :rtype: bool
    """
    structure_changed = False
    for sample_index in range(len(original_data_forms)):
        original_data_form, new_name_forms = original_data_forms[sample_index], new_name_form_lists[sample_index]
        if original_data_form.is_valid():
            number_of_pieces = original_data_form.cleaned_data["number_of_pieces"]
            if number_of_pieces < len(new_name_forms):
                del new_name_forms[number_of_pieces:]
                structure_changed = True
            elif number_of_pieces > len(new_name_forms):
                for new_name_index in range(len(new_name_forms), number_of_pieces):
                    new_name_forms.append(NewNameForm(user, readonly=False,
                                                      initial={"new_name": original_data_form.cleaned_data["new_name"]},
                                                      prefix="{0}_{1}".format(sample_index, new_name_index)))
                structure_changed = True
    return structure_changed


def save_to_database(original_data_forms, new_name_form_lists, global_new_data_form, deposition):
    """Performs all splits – if any – and renames the samples according to
    what was input by the user.

    :param original_data_forms: all old samples and pieces numbers
    :param new_name_form_lists: new names for all pieces
    :param global_new_data_form: the global, overriding settings
    :param deposition: the deposition after which the splits took place

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of list of `NewNameForm`
    :type global_new_data_form: `GlobalNewDataForm`
    :type deposition: `samples.models.Deposition`

    :return:
      all sample splits that were performed; note that they are always
      complete, i.e. a sample death objects is always created, too

    :rtype: list of `samples.models.SampleSplit`
    """
    global_new_location = global_new_data_form.cleaned_data["new_location"]
    sample_splits = []
    for original_data_form, new_name_forms in zip(original_data_forms, new_name_form_lists):
        sample = original_data_form.cleaned_data["sample"]
        new_name = original_data_form.cleaned_data["new_name"]
        if new_name != sample.name:
            # FixMe: Once we have assured that split-after-deposition is only
            # called once per deposition, the second condition (after the
            # "and") is superfluous.
            if not sample.name.startswith("*") and \
                    not models.SampleAlias.objects.filter(name=sample.name, sample=sample).exists():
                models.SampleAlias(name=sample.name, sample=sample).save()
            sample.name = new_name
            sample.save()
        if original_data_form.cleaned_data["number_of_pieces"] > 1:
            sample_split = models.SampleSplit(timestamp=deposition.timestamp + datetime.timedelta(seconds=5),
                                              operator=deposition.operator, parent=sample)
            sample_split.save()
            sample.processes.add(sample_split)
            sample_splits.append(sample_split)
            for new_name_form in new_name_forms:
                child_sample = sample.duplicate()
                child_sample.name = new_name_form.cleaned_data["new_name"]
                child_sample.split_origin = sample_split
                if global_new_location:
                    child_sample.current_location = global_new_location
                child_sample.save()
                for watcher in sample.watchers.all():
                    watcher.my_samples.add(child_sample)
            sample.watchers.clear()
            death = models.SampleDeath(timestamp=deposition.timestamp + datetime.timedelta(seconds=10),
                                       operator=deposition.operator, reason="split")
            death.save()
            sample.processes.add(death)
        else:
            if global_new_location:
                sample.current_location = global_new_location
            sample.save()
    deposition.split_done = True
    deposition.save()
    return sample_splits


def is_referentially_valid(original_data_forms, new_name_form_lists, deposition):
    """Test whether all forms are consistent with each other and with the
    database.  For example, no sample name must occur twice, and the sample
    names must not exist within the database already.

    :param original_data_forms: all old samples and pieces numbers
    :param new_name_form_lists: new names for all pieces
    :param deposition: the deposition after which the split takes place

    :type original_data_forms: list of `OriginalDataForm`
    :type new_name_form_lists: list of `NewNameForm`
    :type deposition: `samples.models.Deposition`

    :return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    samples = list(deposition.samples.all())
    more_than_one_piece = len(original_data_forms) > 1
    new_names = set()
    original_samples = set()
    for original_data_form in original_data_forms:
        if original_data_form.is_valid():
            original_sample = original_data_form.cleaned_data["sample"]
            if original_sample in original_samples:
                original_data_form.add_error("sample", ValidationError(
                    _("Sample %(sample)s occurs multiple times."), params={"sample": original_sample}, code="invalid"))
                referentially_valid = False
            original_samples.add(original_sample)
            if original_sample not in samples:
                original_data_form.add_error("sample", ValidationError(
                    _("Sample %(sample)s doesn't belong to this deposition."), params={"sample": original_sample},
                    code="invalid"))
                referentially_valid = False
            new_name = original_data_form.cleaned_data["new_name"]
            if new_name in new_names:
                original_data_form.add_error("new_name", ValidationError(
                    _("This sample name has been used already on this page."), code="invalid"))
                referentially_valid = False
            new_names.add(new_name)
            if more_than_one_piece and new_name == deposition.number:
                original_data_form.add_error("new_name", ValidationError(
                    _("Since there is more than one piece, the new name must not be exactly the deposition's name."),
                    code="invalid"))
                referentially_valid = False
    if all(original_data_form.is_valid() for original_data_form in original_data_forms):
        assert len(original_samples) <= len(samples)
        if len(original_samples) < len(samples):
            original_data_form.add_error(None, ValidationError(
                _("At least one sample of the original deposition is missing."), code="required"))
            referentially_valid = False
    for new_name_forms, original_data_form in zip(new_name_form_lists, original_data_forms):
        if original_data_form.is_valid():
            original_sample = original_data_form.cleaned_data["sample"]
            if deposition != original_sample.processes.exclude(content_type=ContentType.objects.
                                                               get_for_model(models.Result)) \
                .order_by("-timestamp")[0].actual_instance and original_data_form.cleaned_data["number_of_pieces"] > 1:
                original_data_form.add_error("sample", ValidationError(
                    _("The sample can't be split, because the deposition is not the latest process."), code="invalid"))
                referentially_valid = False
            else:
                for new_name_form in new_name_forms:
                    if new_name_form.is_valid():
                        new_name = new_name_form.cleaned_data["new_name"]
                        if original_data_form.cleaned_data["number_of_pieces"] == 1:
                            if new_name != original_data_form.cleaned_data["new_name"]:
                                new_name_form.add_error("new_name", ValidationError(
                                    _("If you don't split, you can't rename the single piece."), code="invalid"))
                                referentially_valid = False
                        else:
                            if new_name in new_names:
                                new_name_form.add_error("new_name", ValidationError(
                                    _("This sample name has been used already on this page."), code="invalid"))
                                referentially_valid = False
                            new_names.add(new_name)
                            if not new_name.startswith(original_data_form.cleaned_data["new_name"]):
                                new_name_form.add_error("new_name", ValidationError(
                                    _("If you choose a deposition-style name, it must begin with the parent's new name."),
                                    code="invalid"))
                                referentially_valid = False
                            if sample_names.does_sample_exist(new_name):
                                new_name_form.add_error("new_name", ValidationError(_("This sample name exists already."),
                                                                                    code="duplicate"))
                                referentially_valid = False
    return referentially_valid


def forms_from_post_data(user, post_data, deposition, remote_client):
    """Intepret the POST data and create bound forms for old and new names and
    the global data.  The top-level new-data list has the same number of
    elements as the original-data list because they correspond to each other.

    :param user: the current user
    :param post_data: the result from ``request.POST``
    :param deposition: the deposition after which this split takes place
    :param remote_client: whether the request was sent from the JuliaBase remote
        client

    :type user: django.contrib.auth.models.User
    :type post_data: QueryDict
    :type deposition: `samples.models.Deposition`
    :type remote_client: bool

    :return:
      list of original data (i.e. old names) of every sample, list of lists of
      the new data (i.e. piece names), global new data

    :rtype: list of `OriginalDataForm`, list of lists of `NewNameForm`,
      `GlobalNewDataForm`
    """
    post_data, number_of_samples, list_of_number_of_new_names = utils.normalize_prefixes(post_data)
    original_data_forms = [OriginalDataForm(remote_client, deposition.number, post_data, prefix=str(i))
                           for i in range(number_of_samples)]
    new_name_form_lists = []
    for sample_index, original_data_form in enumerate(original_data_forms):
        number_of_pieces = original_data_form.cleaned_data["number_of_pieces"] if original_data_form.is_valid() else None
        new_name_forms = []
        for new_name_index in range(list_of_number_of_new_names[sample_index]):
            prefix = "{0}_{1}".format(sample_index, new_name_index)
            new_name_form = \
                NewNameForm(user, readonly=number_of_pieces == 1, data=post_data, prefix=prefix)
            if number_of_pieces == 1 and new_name_form.is_valid() and original_data_form.is_valid() \
                    and new_name_form.cleaned_data["new_name"] != original_data_form.cleaned_data["new_name"]:
                piece_data = {}
                piece_data["new_name"] = original_data_form.cleaned_data["new_name"]
                new_name_form = NewNameForm(user, readonly=True, initial=piece_data, prefix=prefix)
            new_name_forms.append(new_name_form)
        new_name_form_lists.append(new_name_forms)
    global_new_data_form = GlobalNewDataForm(post_data, deposition_instance=deposition)
    return original_data_forms, new_name_form_lists, global_new_data_form


def forms_from_database(user, deposition, remote_client, new_names):
    """Take a deposition instance and construct forms from it for its old and
    new data.  The top-level new data list has the same number of elements as
    the old data list because they correspond to each other.

    :param user: the current user
    :param deposition: the deposition to be converted to forms.
    :param remote_client: whether the request was sent from the JuliaBase remote
        client
    :param new_names: dictionary which maps sample IDs to suggested new names of
        this sample; by default (i.e., if the sample ID doesn't occur in
        ``new_names``), the suggested new name is the deposition number, or the
        old name iff it is a new-style name

    :type user: django.contrib.auth.models.User
    :type deposition: `samples.models.Deposition`
    :type remote_client: bool
    :type new_names: dict mapping int to str

    :return:
      list of original data (i.e. old names) of every sample, list of lists of
      the new data (i.e. piece names), global new data

    :rtype: list of `OriginalDataForm`, list of lists of `NewNameForm`,
      `GlobalNewDataForm`
    """
    def new_name(sample):
        try:
            return new_names[sample.id]
        except KeyError:
            if sample_names.sample_name_format(sample.name) in sample_names.get_renamable_name_formats() \
            and sample_names.valid_new_sample_name(sample.name, deposition.number):
                name_postfix = ""
                try:
                    sample_positions = deposition.sample_positions
                except AttributeError:
                    pass
                else:
                    if sample_positions and sample_positions.get(str(sample.id)):
                        name_postfix = "-{0}".format(sample_positions[str(sample.id)])
                return deposition.number + name_postfix
            else:
                return sample.name
    samples = deposition.samples.all()
    original_data_forms = [OriginalDataForm(remote_client, new_name(sample),
                                            initial={"sample": sample.name, "new_name": new_name(sample)},
                                            prefix=str(i))
                           for i, sample in enumerate(samples)]
    new_name_form_lists = [[NewNameForm(user, readonly=True, initial={"new_name": new_name(sample)}, prefix="{0}_0".
                                        format(i))]
                           for i, sample in enumerate(samples)]
    global_new_data_form = GlobalNewDataForm(deposition_instance=deposition)
    return original_data_forms, new_name_form_lists, global_new_data_form


@login_required
@unquote_view_parameters
def split_and_rename_after_deposition(request, deposition_number):
    """View for renaming and/or splitting samples immediately after they have
    been deposited in the same run.

    Optionally, you can give query string parameters of the form
    ``new-name-21=super`` where 21 is the sample ID and “super” is the
    suggested new name of this sample.

    :param request: the current HTTP Request object
    :param deposition_number: the number of the deposition after which samples
        should be split and/or renamed

    :type request: HttpRequest
    :type deposition_number: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    deposition = get_object_or_404(models.Deposition, number=deposition_number).actual_instance
    permissions.assert_can_edit_physical_process(request.user, deposition)
    if not deposition.finished:
        raise Http404("This deposition is not finished yet.")
    if deposition.split_done:
        raise Http404("You can use the split and rename function only once after a deposition.")
    remote_client = is_json_requested(request)
    if request.POST:
        original_data_forms, new_name_form_lists, global_new_data_form = \
            forms_from_post_data(request.user, request.POST, deposition, remote_client)
        all_valid = is_all_valid(original_data_forms, new_name_form_lists, global_new_data_form)
        structure_changed = change_structure(request.user, original_data_forms, new_name_form_lists)
        referentially_valid = is_referentially_valid(original_data_forms, new_name_form_lists, deposition)
        if all_valid and referentially_valid and not structure_changed:
            sample_splits = save_to_database(original_data_forms, new_name_form_lists, global_new_data_form, deposition)
            for sample_split in sample_splits:
                utils.Reporter(request.user).report_sample_split(sample_split, sample_completely_split=True)
            return utils.successful_response(request, _("Samples were successfully split and/or renamed."),
                                             json_response=True)
    else:
        new_names = {int_or_zero(key[len("new-name-"):]): new_name
                     for key, new_name in request.GET.items() if key.startswith("new-name-")}
        new_names.pop(0, None)
        original_data_forms, new_name_form_lists, global_new_data_form = \
            forms_from_database(request.user, deposition, remote_client, new_names)
    return render(request, "samples/split_after_deposition.html",
                  {"title": _("Bulk sample rename for {deposition}").format(deposition=deposition),
                   "samples": list(zip(original_data_forms, new_name_form_lists)),
                   "new_sample_data": global_new_data_form})


_ = ugettext
