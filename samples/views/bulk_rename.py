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


"""View for bulk-renaming samples with a provisional sample name.  The new
names must be “new-style” names.  It is also possible, however, to use this
view just to rename *one* sample (but it *must* have a provisional name).
"""

import datetime, string, itertools
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.http import Http404
import django.utils.http
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy as _, ugettext, ungettext
from django.forms.utils import ValidationError
from django.contrib import messages
from jb_common.utils.base import format_enumeration
from samples import models, permissions
import samples.utils.views as utils
from samples.utils import sample_names


class PrefixesForm(forms.Form):
    """Form for giving the prefix to be used for the new names.  This form is
    not used if the user has only his own initials available, i.e. there is no
    external operator with own initials connected with this user.

    Prefixes may be ``10-TB-`` or ``ACME-`` (for external operators).
    """
    prefix = forms.ChoiceField(label=_("Prefix"))

    def __init__(self, available_prefixes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prefix"].choices = available_prefixes


class NewNameForm(forms.Form):
    """Form for the new name of one sample.
    """
    name = forms.CharField(label=_("New name"), max_length=22)
    save_alias = forms.BooleanField(label=_("Save old name as alias"), required=False,
                                    initial=True)

    def __init__(self, user, prefix_, sample, *args, **kwargs):
        """
        :param user: The user that requests the renaming.
        :param prefix_: The prefix to be used.  If, for some reason, there is no
            prefix available, give an empty string.  Validation will then fail,
            however, it would fail for the whole page anyway without a prefix.
        :param sample: The sample to be renamed.

        :type user: django.contrib.auth.models.User
        :type prefix_: str
        :type sample: samples.models.Sample
        """
        super().__init__(*args, **kwargs)
        self.prefix_ = prefix_
        old_name_format = sample_names.sample_name_format(sample.name)
        if old_name_format:
            self.possible_new_name_formats = settings.SAMPLE_NAME_FORMATS[old_name_format].get("possible_renames", set())
        else:
            self.possible_new_name_formats = set()
        self.user = user

    def clean_name(self):
        new_name = self.prefix_ + self.cleaned_data["name"]
        name_format, match = sample_names.sample_name_format(new_name, with_match_object=True)
        if name_format not in self.possible_new_name_formats:
            error_message = ungettext("New name must be a valid “%(sample_formats)s” name.",
                                      "New name must be a valid name of one of these types: %(sample_formats)s.",
                                      len(self.possible_new_name_formats))
            raise ValidationError(error_message,
                params={"sample_formats": format_enumeration(
                    sample_names.verbose_sample_name_format(name_format) for name_format in self.possible_new_name_formats)},
                code="invalid")
        utils.check_sample_name(match, self.user)
        if sample_names.does_sample_exist(new_name):
            raise ValidationError(_("This sample name exists already."), code="duplicate")
        return new_name


def is_referentially_valid(samples, new_name_forms):
    """Check whether there are duplicate names on the page.  Note that I don't
    check here wheter samples with these names already exist in the database.
    This is done in the form itself.

    :param samples: the samples to be re-named
    :param new_name_forms: all forms with the new names

    :type samples: list of `samples.models.Sample`
    :type new_name_forms: list of `NewNameForm`

    :return:
      whether there were no duplicates on the page, and whether no old-style
      names are renamed to external names

    :rtype: bool
    """
    referentially_valid = True
    new_names = set()
    for sample, new_name_form in zip(samples, new_name_forms):
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["name"]
            if new_name in new_names:
                new_name_form.add_error("name", ValidationError(_("This sample name has been used already on this page."),
                                                                code="invalid"))
                referentially_valid = False
            else:
                new_names.add(new_name)
    return referentially_valid


def find_prefixes(user):
    """Generates all possible sample name prefixes for the user.  The templates for
    this are taken from ``settings.NAME_PREFIX_TEMPLATES``.  Note that it makes
    sense to define such prefixes only if you allow sample name formats that
    also contain these prefixes.

    :param user: the currently logged-in user

    :type user: django.contrib.auth.models.User

    :return:
      all possible sample name prefixes for this user

    :rtype: list of str
    """
    substitution_axes = []
    year = datetime.datetime.today().strftime("%Y")
    substitution_axes.append([("year", year)])
    substitution_axes.append([("short_year", year[2:])])
    try:
        substitution_axes.append([("user_initials", user.initials.initials)])
    except models.Initials.DoesNotExist:
        pass
    external_contact_initials = models.Initials.objects.filter(external_operator__contact_persons=user)
    if external_contact_initials.exists():
        substitution_axes.append([("external_contact_initials", initials) for initials in external_contact_initials])
    prefixes = set()
    for format_string in settings.NAME_PREFIX_TEMPLATES:
        for substitutions in itertools.product(*substitution_axes):
            try:
                prefix = format_string.format(**dict(substitutions))
            except KeyError:
                pass
            else:
                prefixes.add(prefix)
    result = []
    for prefix in sorted(prefixes):
        if prefix == "":
            result.append(("*", ""))
        else:
            result.append((prefix, prefix))
    return result


@login_required
def bulk_rename(request):
    """View for bulk-renaming samples that have had a provisional name so far.  If
    the user doesn't have initials yet, he is redirected to his preferences
    page.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    # FixMe: Get rid of the "numbers" parameter.  I think it is only used in
    # the remote client.
    if "numbers" in request.GET:
        numbers_list = request.GET.get("numbers", "")
        samples = [get_object_or_404(models.Sample, name="*" + number.zfill(5)) for number in numbers_list.split(",")]
    elif "ids" in request.GET:
        ids = request.GET["ids"].split(",")
        samples = [get_object_or_404(models.Sample, pk=utils.convert_id_to_int(id_)) for id_ in ids]
        if not all(sample_names.sample_name_format(sample.name) in sample_names.get_renamable_name_formats()
                   for sample in samples):
            raise Http404("Some given samples cannot be renamed.")
    else:
        samples = None
    if not samples:
        raise Http404("No samples given.")
    for sample in samples:
        permissions.assert_can_edit_sample(request.user, sample)

    available_prefixes = find_prefixes(request.user)
    if not available_prefixes and any("{user_initials}" in format_ for format_ in settings.NAME_PREFIX_TEMPLATES) \
       and not models.Initials.objects.filter(user=request.user).exists():
        query_string = "initials_mandatory=True&next=" + django.utils.http.urlquote_plus(
            request.path + "?" + request.META["QUERY_STRING"], safe="/")
        messages.info(request, _("You may change the sample names, but you must choose initials first."))
        return utils.successful_response(request, view="samples:edit_preferences",
                                         kwargs={"login_name": request.user.username},
                                         query_string=query_string, forced=True)
    single_prefix = available_prefixes[0][1] if len(available_prefixes) == 1 else None
    if request.method == "POST":
        if single_prefix:
            prefixes_form = None
            prefix = single_prefix
        elif available_prefixes:
            prefixes_form = PrefixesForm(available_prefixes, request.POST)
            prefix = prefixes_form.cleaned_data["prefix"] if prefixes_form.is_valid() else ""
        else:
            prefixes_form = None
            prefix = ""
        if prefix == "*":
            prefix = ""
        new_name_forms = [NewNameForm(request.user, prefix, sample, request.POST, prefix=str(sample.pk))
                          for sample in samples]
        all_valid = prefixes_form is None or prefixes_form.is_valid()
        all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms]) and all_valid
        referentially_valid = is_referentially_valid(samples, new_name_forms)
        if all_valid and referentially_valid:
            for sample, new_name_form in zip(samples, new_name_forms):
                if not sample.name.startswith("*") and new_name_form.cleaned_data["save_alias"]:
                    models.SampleAlias(name=sample.name, sample=sample).save()
                sample.name = new_name_form.cleaned_data["name"]
                sample.save()
            return utils.successful_response(request, _("Successfully renamed the samples."))
    else:
        prefixes_form = PrefixesForm(available_prefixes, initial={"prefix": available_prefixes[0][0]}) \
                            if available_prefixes else None
        new_name_forms = [NewNameForm(request.user, "", sample, prefix=str(sample.pk)) for sample in samples]
    return render(request, "samples/bulk_rename.html",
                  {"title": _("Rename samples"),
                   "prefixes": prefixes_form, "single_prefix": single_prefix,
                   "samples": list(zip(samples, new_name_forms))})


_ = ugettext
