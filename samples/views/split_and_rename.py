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


"""Here are the views for an ordinary sample split.
"""

import datetime
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from django import forms
from django.contrib.auth.decorators import login_required
import django.utils.timezone
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.utils.text import capfirst
from django.forms.utils import ValidationError
from jb_common.utils.base import respond_in_json, format_enumeration, unquote_view_parameters, help_link
from samples import models, permissions
import samples.utils.views as utils
from samples.utils import sample_names


class NewNameForm(forms.Form):
    """Form for data of one new sample piece.
    """
    new_name = forms.CharField(label=capfirst(_("new sample name")), max_length=30)
    new_purpose = forms.CharField(label=_("New sample purpose"), max_length=80, required=False)
    delete = forms.BooleanField(label=_("Delete"), required=False)

    def __init__(self, user, parent_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_name = parent_name
        parent_name_format = sample_names.sample_name_format(parent_name)
        if parent_name_format:
            self.possible_new_name_formats = settings.SAMPLE_NAME_FORMATS[parent_name_format].get("possible_renames", set())
        else:
            self.possible_new_name_formats = set()
        self.user = user

    def clean_new_name(self):
        new_name = self.cleaned_data["new_name"]
        sample_name_format, match = sample_names.sample_name_format(new_name, with_match_object=True)
        if not sample_name_format:
            raise ValidationError(_("The sample name has an invalid format."), code="invalid")
        elif not new_name.startswith(self.parent_name):
            if sample_name_format not in self.possible_new_name_formats:
                error_message = _("The new sample name must start with the parent sample's name.")
                params = {}
                if self.possible_new_name_formats:
                    further_error_message = ungettext("  Alternatively, it must be a valid “%(sample_formats)s” name.",
                                                      "  Alternatively, it must be a valid name of one of these types: "
                                                      "%(sample_formats)s", len(self.possible_new_name_formats))
                    error_message += further_error_message
                    params.update({"sample_formats": format_enumeration(
                        sample_names.verbose_sample_name_format(name_format)
                        for name_format in self.possible_new_name_formats)})
                raise ValidationError(error_message, params=params, code="invalid")
            utils.check_sample_name(match, self.user)
        if sample_names.does_sample_exist(new_name):
            raise ValidationError(_("Name does already exist in database."), code="duplicate")
        return new_name


class GlobalDataForm(forms.Form):
    """Form for general data for a split as a whole, and for the “finished”
    checkbox.
    """
    finished = forms.BooleanField(label=_("All pieces completely entered"), required=False)
    sample_completely_split = forms.BooleanField(label=capfirst(_("sample was completely split")), initial=True,
                                                 required=False)
    sample_series = forms.ModelChoiceField(label=capfirst(_("sample series")), queryset=None, required=False)

    def __init__(self, parent, user_details, data=None, **kwargs):
        super().__init__(data, **kwargs)
        now = django.utils.timezone.now() + datetime.timedelta(seconds=5)
        three_months_ago = now - datetime.timedelta(days=90)
        self.fields["sample_series"].queryset = permissions.get_editable_sample_series(user_details.user)


class AutomaticSplitForm(forms.Form):
    """Form for entering data for automatic splitting.  Currently, JuliaBase only
    supports entering a number, and the pieces are generated and automatically
    numbers up to that number.
    """
    number = forms.IntegerField(label=_("Number of pieces"), required=False, max_value=100, min_value=1,
                                widget=forms.NumberInput(attrs={"size": "3"}),
                                help_text=_("the pieces are automatically added, and an index – starting at 1 – is appended"))


def forms_from_post_data(post_data, parent, user):
    """Interpret the POST data sent by the user through his browser and create
    forms from it.  This function also performs the so-called “structural
    changes”, namely adding and deleting pieces.

    Note this this routine doesn't append the dummy form at the end which can
    be used by the user to add a new piece.  On the contrary, it ignores it in
    the POST data if the user didn't make use of it.

    :param post_data: the value of ``request.POST``
    :param parent: the parent sample which is split
    :param user: the current user

    :type post_data: QueryDict
    :type parent: `samples.models.Sample`
    :type user: django.contrib.auth.models.User

    :return:
      The list of the pieces forms, the global data form, and whether the
      structure was changed by the user, the prefix suitable for the
      “add-new-name” form

    :rtype: list of `NewNameForm`, `GlobalDataForm`, `AutomaticSplitForm`, bool, str
    """
    try:
        indices = [int(key.partition("-")[0]) for key in post_data if key.endswith("-new_name")]
    except ValueError:
        indices = []
    indices.sort()
    last_name = None
    new_name_forms = []
    structure_changed = False
    index = 0
    for index in indices:
        if "{0}-delete".format(index) in post_data:
            structure_changed = True
            last_name = None
        else:
            new_name_forms.append(NewNameForm(user, parent.name, post_data, prefix=str(index)))
            last_name = post_data["{0}-new_name".format(index)]
    if new_name_forms:
        if last_name == parent.name:
            del new_name_forms[-1]
        else:
            structure_changed = True
    automatic_split_form = AutomaticSplitForm(post_data)
    if automatic_split_form.is_valid():
        number = automatic_split_form.cleaned_data["number"] or 0
        number_of_digits = len(str(number))
        format_string = "{{}}-{{:0{}}}".format(number_of_digits)
        for piece_number in range(1, number + 1):
            index += 1
            new_name_forms.append(NewNameForm(user, parent.name, None, prefix=str(index),
                                              initial={"new_name": format_string.format(parent.name, piece_number)}))
        automatic_split_form = AutomaticSplitForm()
    next_prefix = str(index + 1)
    global_data_form = GlobalDataForm(parent, user.samples_user_details, post_data)
    return new_name_forms, global_data_form, automatic_split_form, structure_changed, next_prefix


def forms_from_database(parent, user):
    """Generate pristine forms for the given parent.  In particular, this
    returns an empty list of ``new_name_forms``.

    :param parent: the sample to be split
    :param user: the current user

    :type parent: `samples.models.Sample`
    :type user: django.contrib.auth.models.User

    :return:
      the initial ``new_name_forms``, the initial ``global_data_form``,
      the initial ``automatic_split_form``

    :rtype: list of `NewNameForm`, `GlobalDataForm`, `AutomaticSplitForm`
    """
    new_name_forms = []
    global_data_form = GlobalDataForm(parent, user.samples_user_details)
    automatic_split_form = AutomaticSplitForm()
    return new_name_forms, global_data_form, automatic_split_form


def is_all_valid(new_name_forms, global_data_form, automatic_split_form):
    """Tests the “inner” validity of all forms belonging to this view.  This
    function calls the ``is_valid()`` method of all forms, even if one of them
    returns ``False`` (and makes the return value clear prematurely).

    :param new_name_forms: all “new name forms”, but not the dummy one for new
        pieces (the one in darker grey).
    :param global_data_form: the global data form
    :param automatic_split_form: the form for automatic pieces generation

    :type new_name_forms: list of `NewNameForm`
    :type global_data_form: `GlobalDataForm`
    :type automatic_split_form: `AutomaticSplitForm`

    :return:
      whether all forms are valid

    :rtype: bool
    """
    all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms])
    all_valid = global_data_form.is_valid() and all_valid  # Ordering important: .is_valid() must be called
    all_valid = (not automatic_split_form.is_bound or automatic_split_form.is_valid()) and all_valid
    return all_valid


def is_referentially_valid(new_name_forms, global_data_form, number_of_old_pieces):
    """Test whether all forms are consistent with each other and with the
    database.  For example, no piece name must occur twice, and the piece names
    must not exist within the database.

    :param new_name_forms: all “new name forms”, but not the dummy one for new
        pieces (the one in darker grey).
    :param global_data_form: the global data form
    :param number_of_old_pieces: The number of pieces the split has already had,
        if it is a re-split.  It's 0 if we are creating a new split.

    :type new_name_forms: list of `NewNameForm`
    :type global_data_form: `GlobalDataForm`
    :type number_of_old_pieces: int

    :return:
      whether all forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = global_data_form.cleaned_data["finished"]
    if not new_name_forms:
        global_data_form.add_error(None, ValidationError(_("You must split into at least one piece."), code="required"))
        referentially_valid = False
    if global_data_form.is_valid() and global_data_form.cleaned_data["sample_completely_split"] and \
            number_of_old_pieces + len(new_name_forms) < 2:
        global_data_form.add_error(None, ValidationError(
            _("You must split into at least two pieces if the split is complete."), code="required"))
        referentially_valid = False
    new_names = set()
    for new_name_form in new_name_forms:
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["new_name"]
            if new_name in new_names:
                new_name_form.add_error(None, ValidationError(_("Name is already given."), code="invalid"))
                referentially_valid = False
            new_names.add(new_name)
    return referentially_valid


def save_to_database(new_name_forms, global_data_form, parent, sample_split, user):
    """Save all form data to the database.  If `sample_split` is not ``None``,
    modify it instead of appending a new one.  Warning: For this, the old split
    process must be the last process at all for the parental sample!  This must
    be checked before this routine is called.

    :param new_name_forms: all “new name forms”, but not the dummy one for new
        pieces (the one in darker grey).
    :param global_data_form: the global data form
    :param parent: the sample to be split
    :param sample_split: the already existing sample split process that is to be
        modified.  If this is ``None``, create a new one.
    :param user: the current user

    :type new_name_forms: list of `NewNameForm`
    :type global_data_form: `GlobalDataForm`
    :type parent: `samples.models.Sample`
    :type sample_split: `samples.models.SampleSplit`
    :type user: django.contrib.auth.models.User

    :return:
      the sample split instance, new pieces as a dictionary mapping the new
      names to the sample IDs

    :rtype: `samples.models.SampleSplit`, dict mapping str to int
    """
    now = django.utils.timezone.now()
    if not sample_split:
        sample_split = models.SampleSplit(timestamp=now, operator=user, parent=parent)
        sample_split.save()
        parent.processes.add(sample_split)
    else:
        sample_split.timestamp = now
        sample_split.operator = user
        sample_split.save()
    sample_series = global_data_form.cleaned_data["sample_series"]
    new_pieces = {}
    for new_name_form in new_name_forms:
        new_name = new_name_form.cleaned_data["new_name"]
        child = models.Sample(name=new_name,
                              current_location=parent.current_location,
                              currently_responsible_person=user,
                              purpose=new_name_form.cleaned_data["new_purpose"], tags=parent.tags,
                              split_origin=sample_split,
                              topic=parent.topic)
        child.save()
        new_pieces[new_name] = child.pk
        for watcher in parent.watchers.all():
            watcher.my_samples.add(child)
        if sample_series:
            sample_series.samples.add(child)
    if global_data_form.cleaned_data["sample_completely_split"]:
        parent.watchers.clear()
        death = models.SampleDeath(timestamp=now + datetime.timedelta(seconds=5), operator=user, reason="split")
        death.save()
        parent.processes.add(death)
    return sample_split, new_pieces


@help_link("demo.html#split-a-sample")
@login_required
@unquote_view_parameters
def split_and_rename(request, parent_name=None, old_split_id=None):
    """Both splitting of a sample and re-split of an already existing split
    are handled here.  *Either* ``parent_name`` *or* ``old_split`` are unequal
    to ``None``.

    :param request: the current HTTP Request object
    :param parent_name: if given, the name of the sample to be split
    :param old_split_id: if given the process ID of the split to be modified

    :type request: HttpRequest
    :type parent_name: str or NoneType
    :type old_split_id: int or NoneType

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    assert (parent_name or old_split_id) and not (parent_name and old_split_id)
    if parent_name:
        old_split = None
        parent = utils.lookup_sample(parent_name, request.user)
    else:
        old_split = get_object_or_404(models.SampleSplit, pk=utils.convert_id_to_int(old_split_id))
        parent = old_split.parent
        permissions.assert_can_edit_sample(request.user, parent)
        if parent.last_process_if_split() != old_split:
            raise Http404("This split is not the last one in the sample's process list.")
    number_of_old_pieces = old_split.pieces.count() if old_split else 0
    automatic_split_form = AutomaticSplitForm(request.POST)
    if request.method == "POST":
        new_name_forms, global_data_form, automatic_split_form, structure_changed, next_prefix = \
            forms_from_post_data(request.POST, parent, request.user)
        all_valid = is_all_valid(new_name_forms, global_data_form, automatic_split_form)
        referentially_valid = is_referentially_valid(new_name_forms, global_data_form, number_of_old_pieces)
        if all_valid and referentially_valid and not structure_changed:
            sample_split, new_pieces = save_to_database(new_name_forms, global_data_form, parent, old_split, request.user)
            utils.Reporter(request.user).report_sample_split(
                sample_split, global_data_form.cleaned_data["sample_completely_split"])
            return utils.successful_response(
                request, _("Sample “{sample}” was successfully split.").format(sample=parent),
                "samples:show_sample_by_name", {"sample_name": parent.name}, json_response=new_pieces)
    else:
        new_name_forms, global_data_form, automatic_split_form = forms_from_database(parent, request.user)
        next_prefix = "0"
    new_name_forms.append(NewNameForm(request.user, parent.name,
                                      initial={"new_name": parent.name, "new_purpose": parent.purpose},
                                      prefix=next_prefix))
    return render(request, "samples/split_and_rename.html",
                  {"title": _("Split sample “{sample}”").format(sample=parent),
                   "new_names": list(zip(range(number_of_old_pieces + 1,
                                               number_of_old_pieces + 1 + len(new_name_forms)),
                                         new_name_forms)),
                   "automatic_split": automatic_split_form,
                   "global_data": global_data_form,
                   "old_split": old_split})


@login_required
@unquote_view_parameters
def latest_split(request, sample_name):
    """Get the database ID of the latest split of a sample, if it is also the
    very latest process for that sample.  In all other cases, return ``None``
    (or an error HTML page if the sample didn't exist).

    :param request: the current HTTP Request object
    :param sample_name: the name of the sample

    :type request: HttpRequest
    :type sample_name: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    sample = utils.lookup_sample(sample_name, request.user)
    split = sample.last_process_if_split()
    return respond_in_json(split.pk if split else None)


_ = ugettext
