#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""View for bulk-renaming samples with a provisional sample name.  The new
names must be “new-style” names.  It is also possible, however, to use this
view just to rename *one* sample (but it *must* have a provisional name).
"""

import datetime
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import Http404
import django.utils.http
from django import forms
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ugettext_lazy
from django.forms.util import ValidationError
from chantal.samples import models, permissions
from chantal.samples.views import utils

class InitialsForm(forms.Form):
    u"""Form for giving the initials to be used for the new names.  This form
    is not used if the user has only his own initials available, i.e. there is
    no external operator with own initials connected with this user.
    """
    _ = ugettext_lazy
    initials = forms.ChoiceField(label=_(u"Initials"))
    def __init__(self, available_initials, *args, **kwargs):
        super(InitialsForm, self).__init__(*args, **kwargs)
        self.fields["initials"].choices = available_initials

class NewNameForm(forms.Form):
    u"""Form for the new name of one sample.
    """
    _ = ugettext_lazy
    name = forms.CharField(label=_(u"New name"), max_length=22)
    def __init__(self, year, initials, *args, **kwargs):
        u"""Class constructor.

        :Parameters:
          - `year`: the two-digit year of origin
          - `initials`: The initials to be used.  If, for some reason, there
            are no initials available, give an empty string.  Validation will
            the fail, however, it would fail for the whole page anyway without
            initials.

        :type year: str
        :type initials: str
        """
        super(NewNameForm, self).__init__(*args, **kwargs)
        self.prefix_ = "%s-%s-" % (year, initials)
    def clean_name(self):
        new_name = self.prefix_ + self.cleaned_data["name"]
        if utils.sample_name_format(new_name) != "new":
            raise ValidationError(_(u"New name must be a valid “new-style” name."))
        if utils.does_sample_exist(new_name):
            raise ValidationError(_(u"This sample name exists already."))
        return new_name

def is_referentially_valid(new_name_forms):
    u"""Check whether there are duplicate names on the page.  Note that I don't
    check here wheter samples with these names already exist in the database.
    This is done in the form itself.

    :Parameters:
      - `new_name_forms`: all forms with the new names

    :type new_name_forms: list of `NewNameForm`

    :Return:
      whether there were no duplicates on the page.

    :rtype: bool
    """
    referentially_valid = True
    new_names = set()
    for new_name_form in new_name_forms:
        if new_name_form.is_valid():
            new_name = new_name_form.cleaned_data["name"]
            if new_name in new_names:
                utils.append_error(new_name_form, _(u"This sample name has been used already on this page."), "name")
                referentially_valid = False
            else:
                new_names.add(new_name)
    return referentially_valid

@login_required
def bulk_rename(request):
    u"""View for bulk-renaming samples that have had a provisional name so far.
    If the user don't have initials yet, he is redirected to his preferences
    page.
    
    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    try:
        own_initials = request.user.initials
        available_initials = [(own_initials.pk, unicode(own_initials))]
    except models.Initials.DoesNotExist:
        available_initials = []
    numbers_list = utils.parse_query_string(request).get("numbers", "")
    samples = [get_object_or_404(models.Sample, name="*"+number) for number in numbers_list.split(",")]
    if not samples:
        raise Http404(_(u"Please give the list of provisional samples names (without the asterisk, but with leading "
                        u"zeros) as a comma-separated list without whitespace in the “numbers” query string parameter."))
    for sample in samples:
        permissions.assert_can_edit_sample(request.user, sample)
    year = u"%02d" % (datetime.date.today().year % 100)
    for external_operator in request.user.external_contacts.all():
        try:
            operator_initials = external_operator.initials
        except models.Initials.DoesNotExist:
            continue
        available_initials.append((operator_initials.pk, unicode(operator_initials)))
    if not available_initials:
        query_string = "initials_mandatory=True&next=" + django.utils.http.urlquote_plus(
            request.path + "?" + request.META["QUERY_STRING"], safe="/")
        return utils.successful_response(request, _(u"You may change the sample names, but you must choose initials first."),
                                         view="samples.views.user_details.edit_preferences",
                                         kwargs={"login_name": request.user.username},
                                         query_string=query_string, forced=True)
    single_initials = available_initials[0][1] if len(available_initials) == 1 else None
    if request.method == "POST":
        initials_form = InitialsForm(available_initials, request.POST)
        initials = single_initials or (initials_form.cleaned_data["initials"] if initials_form.is_valid() else u"")
        new_name_forms = [NewNameForm(year, initials, request.POST, prefix=str(sample.pk)) for sample in samples]
        all_valid = initials_form.is_valid() or bool(single_initials)
        all_valid = all([new_name_form.is_valid() for new_name_form in new_name_forms]) and all_valid
        referentially_valid = is_referentially_valid(new_name_forms)
        if all_valid and referentially_valid:
            for sample, new_name_form in zip(samples, new_name_forms):
                sample.name = new_name_form.cleaned_data["name"]
                sample.save()
            return utils.successful_response(request, _(u"Successfully renamed the samples."))
    else:
        initials_form = InitialsForm(available_initials, initial={"initials": available_initials[0][0]})
        new_name_forms = [NewNameForm(year, u"", prefix=str(sample.pk)) for sample in samples]
    return render_to_response("bulk_rename.html",
                              {"title": _(u"Giving new-style names"),
                               "initials": initials_form, "single_initials": single_initials,
                               "samples": zip(samples, new_name_forms), "year": year},
                              context_instance=RequestContext(request))
