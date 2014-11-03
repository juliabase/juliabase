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


"""View for bulk-renaming samples with a provisional sample name.  The new
names must be “new-style” names.  It is also possible, however, to use this
view just to rename *one* sample (but it *must* have a provisional name).
"""

from __future__ import absolute_import, unicode_literals

import datetime, string
from django.shortcuts import render_to_response, get_object_or_404
from django.conf import settings
from django.template import RequestContext
from django.http import Http404
import django.utils.http
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy, ungettext
from django.forms.util import ValidationError
from django.contrib import messages
from samples import models, permissions
from samples.views import utils, form_utils


class PrefixesForm(forms.Form):
    """Form for giving the prefix to be used for the new names.  This form is
    not used if the user has only his own initials available, i.e. there is no
    external operator with own initials connected with this user.

    Prefixes may be ``10-TB-`` or ``ACME-`` (for external operators).
    """
    _ = ugettext_lazy
    prefix = forms.ChoiceField(label=_("Prefix"))

    def __init__(self, available_prefixes, *args, **kwargs):
        super(PrefixesForm, self).__init__(*args, **kwargs)
        self.fields["prefix"].choices = available_prefixes


class NewNameForm(forms.Form):
    """Form for the new name of one sample.
    """
    _ = ugettext_lazy
    name = forms.CharField(label=_("New name"), max_length=22)

    def __init__(self, user, prefix_, sample, *args, **kwargs):
        """Class constructor.

        :Parameters:
          - user: The user that requests the renaming.
          - `prefix_`: The prefix to be used.  If, for some reason, there is no
            prefix available, give an empty string.  Validation will then fail,
            however, it would fail for the whole page anyway without a prefix.
          - `sample`: The sample to be renamed.

        :type user: django.contrib.auth.models.User
        :type prefix_: str
        :type sample: samples.models.Sample
        """
        super(NewNameForm, self).__init__(*args, **kwargs)
        self.prefix_ = prefix_
        old_name_format = utils.sample_name_format(sample.name)
        if old_name_format:
            self.possible_new_name_formats = settings.SAMPLE_NAME_FORMATS[old_name_format].get("possible renames", set())
        else:
            self.possible_new_name_formats = set()
        self.user = user

    def clean_name(self):
        new_name = self.prefix_ + self.cleaned_data["name"]
        name_format, match = utils.sample_name_format(new_name, with_match_object=True)
        if name_format not in self.possible_new_name_formats:
            error_message = ungettext("New name must be a valid “{sample_formats}” name.",
                                      "New name must be a valid name of one of these types: {sample_formats}",
                                      len(self.possible_new_name_formats))
            error_message = error_message.format(sample_formats=utils.format_enumeration(
                utils.verbose_sample_name_format(name_format) for name_format in self.possible_new_name_formats))
            raise ValidationError(error_message)
        form_utils.check_sample_name(match, self.user)
        if utils.does_sample_exist(new_name):
            raise ValidationError(_("This sample name exists already."))
        return new_name


def is_referentially_valid(samples, new_name_forms):
    """Check whether there are duplicate names on the page.  Note that I don't
    check here wheter samples with these names already exist in the database.
    This is done in the form itself.

    :Parameters:
      - `samples`: the samples to be re-named
      - `new_name_forms`: all forms with the new names

    :type samples: list of `models.Sample`
    :type new_name_forms: list of `NewNameForm`

    :Return:
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
                new_name_form.add_error("name", _("This sample name has been used already on this page."))
                referentially_valid = False
            else:
                new_names.add(new_name)
    return referentially_valid


def find_prefixes(user):
    """Generates all possible sample name prefixes for the user.  The templates for
    this are taken from `settings.NAME_PREFIX_TEMPLATES`.  Note that it makes
    sense to define such prefixes only if you allow sample name formats that
    also contains these prefixes.

    :Parameters:
      - `user`: the currently logged-in user

    :type user: django.contrib.auth.models.User

    :Returns:
      all possible sample name prefixes for this user

    :rtype: list of str
    """
    def append_prefix(substitutions):
        for format_string in settings.NAME_PREFIX_TEMPLATES:
            try:
                prefix = format_string.format(**substitutions)
            except KeyError:
                pass
            else:
                prefixes.append((prefix, prefix))
    prefixes = []
    year = str(datetime.datetime.today().year)
    substitutions = {"year": year, "short_year": year[2:]}
    try:
        substitutions["user_initials"] = user.initials.initials
    except models.Initials.DoesNotExist:
        pass
    for initials in models.Initials.objects.filter(external_operator__contact_persons=user):
        local_substitutions = substitutions.copy()
        local_substitutions["external_contact_initials"] = initials.initials
        append_prefix(local_substitutions)
    return prefixes


@login_required
def bulk_rename(request):
    """View for bulk-renaming samples that have had a provisional name so far.
    If the user don't have initials yet, he is redirected to his preferences
    page.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    # FixMe: Get rid of the "numbers" parameter.  I think it is only used in
    # the remote client.
    if "numbers" in request.GET:
        numbers_list = request.GET.get("numbers", "")
        samples = [get_object_or_404(models.Sample, name="*" + number.zfill(5)) for number in numbers_list.split(",")]
    elif "ids" in request.GET:
        ids = request.GET["ids"].split(",")
        samples = [get_object_or_404(models.Sample, pk=utils.convert_id_to_int(id_)) for id_ in ids]
        if not all(utils.sample_name_format(sample.name) in utils.renamable_name_formats for sample in samples):
            raise Http404("Some given samples cannot be renamed.")
    else:
        samples = None
    if not samples:
        raise Http404("No samples given.")
    for sample in samples:
        permissions.assert_can_edit_sample(request.user, sample)

    available_prefixes = find_prefixes(request.user)
    if not available_prefixes and any("{user_initials}" in format_ for format_ in settings.NAME_PREFIX_TEMPLATES):
        query_string = "initials_mandatory=True&next=" + django.utils.http.urlquote_plus(
            request.path + "?" + request.META["QUERY_STRING"], safe="/")
        messages.info(request, _("You may change the sample names, but you must choose initials first."))
        return utils.successful_response(request, view="samples.views.user_details.edit_preferences",
                                         kwargs={"login_name": request.user.username},
                                         query_string=query_string, forced=True)
    single_prefix = available_prefixes[0][1] if len(available_prefixes) == 1 else None
    if request.method == "POST":
        if available_prefixes:
            prefixes_form = PrefixesForm(available_prefixes, request.POST)
            prefix = single_prefix or (prefixes_form.cleaned_data["prefix"] if prefixes_form.is_valid() else "")
        else:
            prefixes_form = None
            prefix = ""
        new_name_forms = [NewNameForm(request.user, prefix, sample, request.POST, prefix=str(sample.pk))
                          for sample in samples]
        all_valid = prefixes_form is None or prefixes_form.is_valid()
        all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms]) and all_valid
        referentially_valid = is_referentially_valid(samples, new_name_forms)
        if all_valid and referentially_valid:
            for sample, new_name_form in zip(samples, new_name_forms):
                if not sample.name.startswith("*"):
                    models.SampleAlias(name=sample.name, sample=sample).save()
                sample.name = new_name_form.cleaned_data["name"]
                sample.save()
            return utils.successful_response(request, _("Successfully renamed the samples."))
    else:
        prefixes_form = PrefixesForm(available_prefixes, initial={"prefix": available_prefixes[0][0]}) \
                            if available_prefixes else None
        new_name_forms = [NewNameForm(request.user, "", sample, prefix=str(sample.pk)) for sample in samples]
    return render_to_response("samples/bulk_rename.html",
                              {"title": _("Giving new-style names"),
                               "prefixes": prefixes_form, "single_prefix": single_prefix,
                               "samples": zip(samples, new_name_forms)},
                              context_instance=RequestContext(request))
