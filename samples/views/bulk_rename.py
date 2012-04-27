#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
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
from django.template import RequestContext
from django.http import Http404
import django.utils.http
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from django.contrib import messages
from chantal_common.utils import append_error
from samples import models, permissions
from samples.views import utils


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

    def __init__(self, prefix_, *args, **kwargs):
        """Class constructor.

        :Parameters:
          - `prefix_`: The prefix to be used.  If, for some reason, there is no
            prefix available, give an empty string.  Validation will then fail,
            however, it would fail for the whole page anyway without a prefix.

        :type prefix_: str
        """
        super(NewNameForm, self).__init__(*args, **kwargs)
        self.prefix_ = prefix_

    def clean_name(self):
        new_name = self.prefix_ + self.cleaned_data["name"]
        if utils.sample_name_format(new_name) != "new":
            raise ValidationError(_("New name must be a valid “new-style” name."))
        if utils.does_sample_exist(new_name):
            raise ValidationError(_("This sample name exists already."))
        return new_name


def is_referentially_valid(samples, prefixes_form, new_name_forms):
    """Check whether there are duplicate names on the page.  Note that I don't
    check here wheter samples with these names already exist in the database.
    This is done in the form itself.

    :Parameters:
      - `samples`: the samples to be re-named
      - `prefixes_form`: the form with the selected common prefix
      - `new_name_forms`: all forms with the new names

    :type samples: list of `models.Sample`
    :type prefixes_form: `PrefixesForm`
    :type new_name_forms: list of `NewNameForm`

    :Return:
      whether there were no duplicates on the page, and whether no old-style
      names are renamed to external names

    :rtype: bool
    """
    referentially_valid = True
    new_names = set()
    if prefixes_form.is_valid():
        prefix_is_external = prefixes_form.cleaned_data.get("prefix").startswith(tuple(string.ascii_uppercase))
    else:
        prefix_is_external = False
    for sample, new_name_form in zip(samples, new_name_forms):
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["name"]
            if new_name in new_names:
                append_error(new_name_form, _("This sample name has been used already on this page."), "name")
                referentially_valid = False
            elif utils.sample_name_format(sample.name) != "provisional" and prefix_is_external:
                append_error(new_name_form, _("Only provisional names can be changed to an external name."), "name")
                referentially_valid = False
            else:
                new_names.add(new_name)
    return referentially_valid


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
    year = datetime.date.today().strftime("%y")
    try:
        own_initials = request.user.initials
        own_prefix = "{0}-{1}-".format(year, own_initials)
        available_prefixes = [(own_prefix, own_prefix)]
    except models.Initials.DoesNotExist:
        available_prefixes = []
    # FixMe: Get rid of the "numbers" parameter.  I think it is only used in
    # the remote client.
    if "numbers" in request.GET:
        numbers_list = request.GET.get("numbers", "")
        samples = [get_object_or_404(models.Sample, name="*" + number.zfill(5)) for number in numbers_list.split(",")]
    elif "ids" in request.GET:
        ids = request.GET["ids"].split(",")
        samples = [get_object_or_404(models.Sample, pk=utils.convert_id_to_int(id_)) for id_ in ids]
        if not all(utils.sample_name_format(sample.name) in ["old", "provisional"] for sample in samples):
            raise Http404("Some given samples not found amongst those with old-style names.")
    else:
        samples = None
    if not samples:
        raise Http404("No samples given.")
    for sample in samples:
        permissions.assert_can_edit_sample(request.user, sample)
    for external_operator in request.user.external_contacts.all():
        try:
            operator_initials = external_operator.initials
        except models.Initials.DoesNotExist:
            continue
        prefix = "{0}-".format(operator_initials)
        available_prefixes.append((prefix, prefix))
    if not available_prefixes:
        query_string = "initials_mandatory=True&next=" + django.utils.http.urlquote_plus(
            request.path + "?" + request.META["QUERY_STRING"], safe="/")
        messages.info(request, _("You may change the sample names, but you must choose initials first."))
        return utils.successful_response(request, view="samples.views.user_details.edit_preferences",
                                         kwargs={"login_name": request.user.username},
                                         query_string=query_string, forced=True)
    single_prefix = available_prefixes[0][1] if len(available_prefixes) == 1 else None
    if request.method == "POST":
        prefixes_form = PrefixesForm(available_prefixes, request.POST)
        prefix = single_prefix or (prefixes_form.cleaned_data["prefix"] if prefixes_form.is_valid() else "")
        new_name_forms = [NewNameForm(prefix, request.POST, prefix=str(sample.pk)) for sample in samples]
        all_valid = prefixes_form.is_valid() or bool(single_prefix)
        all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms]) and all_valid
        referentially_valid = is_referentially_valid(samples, prefixes_form, new_name_forms)
        if all_valid and referentially_valid:
            for sample, new_name_form in zip(samples, new_name_forms):
                if not sample.name.startswith("*"):
                    models.SampleAlias(name=sample.name, sample=sample).save()
                sample.name = new_name_form.cleaned_data["name"]
                sample.save()
            return utils.successful_response(request, _("Successfully renamed the samples."))
    else:
        prefixes_form = PrefixesForm(available_prefixes, initial={"prefix": available_prefixes[0][0]})
        new_name_forms = [NewNameForm("", prefix=str(sample.pk)) for sample in samples]
    return render_to_response("samples/bulk_rename.html",
                              {"title": _("Giving new-style names"),
                               "prefixes": prefixes_form, "single_prefix": single_prefix,
                               "samples": zip(samples, new_name_forms), "year": year},
                              context_instance=RequestContext(request))
