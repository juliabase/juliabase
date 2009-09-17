#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Utility classes and routines for form handling.  In particular, all form
classes which are used in more than one module are included here.
"""

from __future__ import absolute_import

from django.utils.translation import ugettext as _, ugettext_lazy, ugettext
from django import forms
from .. import refdb, models


def append_error(form, error_message, fieldname="__all__"):
    u"""This function is called if a validation error is found in form data
    which cannot be found by the ``is_valid`` method itself.  The reason is
    very simple: For many types of invalid data, you must take other forms in
    the same view into account.

    :Parameters:
      - `form`: the form to which the erroneous field belongs
      - `error_message`: the message to be presented to the user
      - `fieldname`: the name of the field that triggered the validation
        error.  It is optional, and if not given, the error is considered an
        error of the form as a whole.

    :type form: ``forms.Form`` or ``forms.ModelForm``.
    :type fieldname: str
    :type error_message: unicode
    """
    # FixMe: Is it really a good idea to call ``is_valid`` here?
    # ``append_error`` is also called in ``clean`` methods after all.
    form.is_valid()
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)


class SelectionBoxForm(forms.Form):
    u"""Form class for the tick box for each reference.  This micro-form is
    generated for each reference in the bulk view.  The actions of the central
    dispatch are performed only on selected references.
    """
    _ = ugettext_lazy
    selected = forms.BooleanField(label=_("selected"), required=False)


output_format_choices = (
    ("ris", u"RIS"),
    ("html", u"HTML"),
    ("xhtml", u"XHTML"),
    ("db31", u"DocBook 3.1"),
    ("db31x", u"DocBook XML 3.1"),
    ("db50", u"DocBook 5.0"),
    ("db50x", u"DocBook XML 3.1"),
    ("teix", u"TEI XML"),
    ("tei5x", u"TEI 5 XML"),
    ("mods", u"MODS"),
    ("bibtex", u"BibTeX"),
    ("rtf", u"RTF")
    )

class ExportForm(forms.Form):
    u"""Form class for exporting references to a particular output format.
    """
    _ = ugettext_lazy
    format = forms.ChoiceField(label=_("Export as"), choices=(("", 9*u"-"),) + output_format_choices, required=False)


class RemoveFromListForm(forms.Form):
    u"""Form class for removing references from a references list.

    The `listname` field is the short name (= RefDB name) of the references
    list.  It is *not* given by the user (therefore, the widget is hidden).
    Instead, it is given an initial value by the creator of the form instance
    in order to have it available when the bound form is processed.

    The underlying problem is that this form is created in the bulk view but
    processed in the dispatch, which means that the information from which list
    should be removed would be lost otherwise.
    """
    _ = ugettext_lazy
    remove = forms.BooleanField(required=False)
    listname = forms.CharField(max_length=255, label=_("List"), widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        verbose_listname = kwargs.pop("verbose_listname", None)
        super(RemoveFromListForm, self).__init__(*args, **kwargs)
        if verbose_listname:
            self.fields["remove"].label = _(u"Remove from list “%s”") % verbose_listname


class AddToShelfForm(forms.Form):
    u"""Form class for adding references to a shelf.
    """
    _ = ugettext_lazy
    new_shelf = forms.ChoiceField(label=_("Add to shelf"), required=False)

    def __init__(self, *args, **kwargs):
        super(AddToShelfForm, self).__init__(*args, **kwargs)
        self.fields["new_shelf"].choices = \
            [("", 9*u"-")] + [(shelf.pk, unicode(shelf)) for shelf in models.Shelf.objects.all()]


class AddToListForm(forms.Form):
    u"""Form class for adding references to a references list.  The user has
    the option to add to an existing list (only `existing_list` is filled) or
    to a new list (only `new_list` is filled).  He must not give both fields.
    """
    _ = ugettext_lazy
    existing_list = forms.ChoiceField(label=_("List"), required=False)
    new_list = forms.CharField(label=_("New list"), max_length=255, required=False)

    def __init__(self, user, *args, **kwargs):
        u"""Class constructor.

        :Parameters:
          - `user`: current user

        :type user: ``django.contrib.auth.models.User``
        """
        super(AddToListForm, self).__init__(*args, **kwargs)
        lists = refdb.get_lists(user)[0]
        self.short_listnames = set(list_[0] for list_ in lists)
        self.fields["existing_list"].choices = [("", 9*"-")] + lists
        self.optional = True

    def clean(self):
        u"""Class clean method which assures that at most one of the fields is
        given.  Additionally, it checks that the name for a new list doesn't
        already exist in the database.
        """
        _ = ugettext
        cleaned_data = self.cleaned_data
        if cleaned_data["existing_list"] and cleaned_data["new_list"]:
            append_error(self, _(u"You must not give both an existing and a new list."), "new_list")
            del cleaned_data["new_list"], cleaned_data["existing_list"]
        elif not self.optional and not cleaned_data["existing_list"] and not cleaned_data["new_list"]:
            append_error(self, _(u"You must give either an existing or a new list."), "new_list")
            del cleaned_data["new_list"], cleaned_data["existing_list"]
        elif cleaned_data["new_list"] and cleaned_data["new_list"] in self.short_listnames:
            append_error(self, _(u"This listname is already given."), "new_list")
            del cleaned_data["new_list"]
        return cleaned_data

