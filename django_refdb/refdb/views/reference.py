#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for viewing, editing, adding, and searching for references.
"""

from __future__ import absolute_import

import os.path, shutil, re, copy, urllib
import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404
from django.views.decorators.http import last_modified
from django import forms
from django.forms.util import ValidationError, ErrorList
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.core.cache import cache
import django.contrib.auth.models
from django.conf import settings
from .. import utils, models

# FixMe: Here, we have two function in one.  This should be disentangled.
def pdf_filepath(reference, user_id=None, existing=False):
    u"""Calculates the absolute filepath of the uploaded PDF in the local
    filesystem.

    :Parameters:
      - `reference`: the reference whose PDF file path should be calculated
      - `user_id`: the ID of the user who tries to retrieve the file; this is
        important because it is possible to upload *private* PDFs.
      - `existing`: Whether the PDF should be existing.  If ``False``, this
        routine returns ``None`` for the filepath if the PDF doesn't exist.

    :type reference: ``pyrefdb.Reference``, with the ``extended_data``
      attribute
    :type user_id: int
    :type existing: bool

    :Return:
      If ``existing==False``, it only returns the absolute path to the uploaded
      PDF file, no matter whether it exists or not.  If ``existing==True``, it
      returns the absolute path (``None`` if not existing) and whether the PDF
      is a private one

    :rtype: unicode or (unicode, bool)
    """
    private = reference.pdf_is_private[user_id] if user_id else False
    if existing and (not private and not reference.global_pdf_available):
        filepath = None
    else:
        directory = os.path.join(settings.MEDIA_ROOT, "references", reference.citation_key)
        if private:
            directory = os.path.join(directory, str(user_id))
        filepath = os.path.join(directory, utils.slugify_reference(reference) + ".pdf")
    return (filepath, private) if existing else filepath


def serialize_authors(authors):
    u"""Converts a list of authors into a string, ready-to-be-used as the
    initial value in an author form field.

    :Parameters:
      - `authors`: the authors

    :type: list of ``pyrefdb.Author``

    :Return:
      the serialised authors, separated by semicolons

    :rtype: unicode
    """
    return u"; ".join(unicode(author) for author in authors)


class CharNoneField(forms.CharField):
    u"""Special form field class which returns ``None`` if the field was not
    filled.  This is interesting because then, the respective RISX field is not
    generated at all.  It may not make any difference but it's cleaner this way
    (at least, easier to debug).
    """

    def clean(self, value):
        return super(CharNoneField, self).clean(value) or None


class MultipleGroupField(forms.MultipleChoiceField):
    u"""Form field class for the selection of groups.
    """

    def set_groups(self, user, additional_groups=frozenset()):
        u"""Set the group list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.  The selection list will
        consist of all currently active groups, plus the given additional group
        if any.  The “currently active groups” are all groups with at least one
        active user amongst its members.

        :Parameters:
          - `user`: the currently logged-in user
          - `additional_groups`: Optional additional groups to be included into
            the list.  Typically, it is the current groups of the reference,
            for example.

        :type user: ``django.contrib.auth.models.User``
        :type additional_groups: set of ``django.contrib.auth.models.Group``
        """
        all_groups = django.contrib.auth.models.Group.objects.filter(user__is_active=True).distinct()
        user_groups = user.groups.all()
        try:
            is_restricted = settings.restricted_group_test
        except AttributeError:
            is_restricted = lambda x: False
        groups = set(group for group in all_groups if not is_restricted(group) or group in user_groups)
        groups |= additional_groups
        groups = sorted(groups, key=lambda group: group.name)
        self.choices = [(group.pk, unicode(group)) for group in groups] or [(u"", 9*u"-")]

    def clean(self, value):
        if value == [u""]:
            value = []
        value = super(MultipleGroupField, self).clean(value)
        return django.contrib.auth.models.Group.objects.in_bulk([int(pk) for pk in set(value)]).values()


date_pattern = re.compile(r"(\d{4})$|(\d{4})-(\d\d?)-(\d\d?)$")
pages_pattern = re.compile(r"(.+?)(?:--(.+))?")

class ReferenceForm(forms.Form):
    u"""Form for editing and adding a reference.
    """

    _ = ugettext_lazy
    reference_type = forms.ChoiceField(label=_("Type"), choices=utils.reference_types.items())
    part_title = CharNoneField(label=_("Part title"), required=False)
    part_authors = forms.CharField(label=_("Part authors"), required=False)
    publication_title = forms.CharField(label=_("Publication title"))
    publication_authors = forms.CharField(label=_("Publication authors"), required=False)
    date = forms.CharField(label=_("Date"), required=False, help_text=_("Either YYYY or YYYY-MM-DD."))
    relevance = forms.TypedChoiceField(label=_("Relevance"), required=False, coerce=int, empty_value=None,
                                       choices=(("", 9*u"-"), (1, "*"), (2, "**"), (3, "***"), (4, "****")))
    volume = CharNoneField(label=_("Volume"), required=False)
    issue = CharNoneField(label=_("Issue"), required=False)
    startpage = CharNoneField(label=_("Start page"), required=False)
    endpage = CharNoneField(label=_("End page"), required=False)
    publisher = CharNoneField(label=_("Publisher"), required=False)
    city = CharNoneField(label=_("Publication place"), required=False)
    address = CharNoneField(label=_("Address"), required=False, help_text=_("Contact address to the author."))
    serial = CharNoneField(label=_("Serial"), required=False)
    doi = CharNoneField(label=_("DOI"), required=False)
    weblink = CharNoneField(label=_("Weblink"), required=False)
    global_notes = forms.CharField(label=_("Global notes"), required=False, widget=forms.Textarea)
    institute_publication = forms.BooleanField(label=_("Institute publication"), required=False)
    has_reprint = forms.BooleanField(label=_("I have a reprint"), required=False)
    abstract = forms.CharField(label=_("Abstract"), required=False, widget=forms.Textarea)
    keywords = forms.CharField(label=_("Keywords"), required=False)
    private_notes = forms.CharField(label=_("Private notes"), required=False, widget=forms.Textarea)
    private_reprint_available = forms.BooleanField(label=_("Private reprint available"), required=False)
    private_reprint_location = CharNoneField(label=_("Private reprint location"), required=False)
    lists = forms.MultipleChoiceField(label=_("Lists"), required=False)
    groups = MultipleGroupField(label=_("Groups"), required=False)
    pdf = forms.FileField(label=_(u"PDF file"), required=False)
    pdf_is_private = forms.BooleanField(label=_("PDF is private"), required=False)

    def __init__(self, request, reference, *args, **kwargs):
        u"""
        :Parameters:
          - `request`: the current HTTP request
          - `reference`: the reference to be edited; if ``None``, add a new one

        :type request: ``HttpRequest``
        :type reference: ``pyrefdb.Reference`` or ``NoneType``
        """
        user = request.user
        initial = kwargs.get("initial") or {}
        lists_choices, lists_initial = utils.get_lists(user, reference.citation_key if reference else None)
        reference_groups = set()
        if reference:
            initial["reference_type"] = reference.type
            if reference.part:
                initial["part_title"] = reference.part.title
                initial["part_authors"] = serialize_authors(reference.part.authors)
            initial["publication_title"] = reference.publication.title
            initial["publication_authors"] = serialize_authors(reference.publication.authors)
            pub_info = reference.publication.pub_info
            if pub_info:
                initial["date"] = unicode(pub_info.pub_date or u"")
                initial["volume"] = pub_info.volume or u""
                initial["issue"] = pub_info.issue or u""
                initial["pages"] = "%s--%s" % (pub_info.startpage, pub_info.endpage) \
                    if pub_info.startpage and pub_info.endpage else pub_info.startpage or u""
                initial["publisher"] = pub_info.publisher or u""
                initial["city"] = pub_info.city or u""
                initial["address"] = pub_info.address or u""
                initial["serial"] = pub_info.serial or u""
                initial["doi"] = pub_info.links.get("doi", u"")
                initial["weblink"] = pub_info.links.get("url", u"")
            initial["institute_publication"] = reference.institute_publication
            initial["relevance"] = reference.relevance
            if reference.comments:
                initial["global_notes"] = reference.comments.content.text
            initial["has_reprint"] = user.pk in reference.users_with_offprint.keywords
            initial["abstract"] = reference.abstract or u""
            initial["keywords"] = u"; ".join(reference.keywords)
            lib_info = reference.get_lib_info(utils.refdb_username(user.id))
            if lib_info:
                initial["private_notes"] = lib_info.notes or u""
                initial["private_reprint_available"] = lib_info.reprint_status == "INFILE"
                initial["private_reprint_location"] = lib_info.availability or u""
            initial["lists"] = lists_initial
            initial["groups"] = reference.groups
        kwargs["initial"] = initial
        super(ReferenceForm, self).__init__(*args, **kwargs)
        self.user = user
        self.reference = reference
        self.refdb_rollback_actions = request.refdb_rollback_actions
        self.fields["lists"].choices = lists_choices
        self.old_lists = lists_initial
        self.fields["groups"].set_groups(user, reference_groups)

    def clean_part_authors(self):
        u"""Cleans the author string.  It is split at the semicolons and then
        parsed into ``Author`` instances.
        
        :Return:
          all authors

        :rtype: list of ``pyrefdb.Author``
        """
        return [pyrefdb.Author(author) for author in self.cleaned_data["part_authors"].split(";")]

    def clean_publication_authors(self):
        u"""Cleans the author string.  It is split at the semicolons and then
        parsed into ``Author`` instances.
        
        :Return:
          all authors

        :rtype: list of ``pyrefdb.Author``
        """
        return [pyrefdb.Author(author) for author in self.cleaned_data["publication_authors"].split(";")]

    def clean_date(self):
        u"""Cleans the date string into a proper ``Date` .

        :Return:
          the given date

        :rytpe: ``pyrefdb.Date``
        """
        date_string = self.cleaned_data["date"]
        if date_string:
            date = pyrefdb.Date()
            match = date_pattern.match(date_string)
            if match:
                if match.group(1):
                    date.year = int(match.group(1))
                else:
                    date.year, date.month, date.day = map(int, match.group(2, 3, 4))
                return date
            else:
                raise ValidationError(_(u"Must be either of the form YYYY or YYYY-MM-DD."))

    def clean_keywords(self):
        u"""Splits the keywords at the semicolons.

        :Return:
          the keywords

        :rtype: list of unicode
        """
        return filter(None, [keyword.strip() for keyword in self.cleaned_data["keywords"].split(";")])

    def clean_private_reprint_available(self):
        return u"INFILE" if self.cleaned_data["private_reprint_available"] else u"NOTINFILE"

    def clean_pdf(self):
        u"""Cleans the field for an uploaded PDF file.  The important thing
        here is that I scan the first four bytes of the file in order to check
        for the magic number of PDF files.

        :Return:
          the original file object, re-opened so that further processing of the
          file starts at the very beginning of the file

        :rtype: ``UploadedFile``
        """
        pdf_file = self.cleaned_data["pdf"]
        if pdf_file:
            if pdf_file.read(4) != "%PDF":
                raise ValidationError(_(u"The uploaded file was not a PDF file."))
            pdf_file.open()
        return pdf_file

    def _forbid_field(self, fieldname, reference_types):
        u"""Generates a form error message if the given field must not be
        filled with data for the selected reference type.  This is an internal
        method only used in `clean`.

        :Parameters:
          - `fieldname`: name of the form field
          - `reference_types`: the reference types for which the field must not
            be filled

        :type fieldname: str
        :type reference_types: list of str
        """
        if self.cleaned_data[fieldname] and self.cleaned_data["reference_type"] in reference_types:
            self._errors[fieldname] = ErrorList([_(u"This field is forbidden for this reference type.")])
            del self.cleaned_data[fieldname]

    def clean(self):
        u"""General clean routine of this form.  Its main task is to detect
        missing or wrongly-filled fields according to the selected reference
        type.  The RIS specification contains (often odd) rules about which
        fields are required, and which fields must not be filled for a given
        reference type.  This is enforced here, among minor other checks.

        :Return:
          the cleaned data

        :rtype: dict mapping str to ``object``
        """
        cleaned_data = self.cleaned_data
        if cleaned_data["endpage"] and not cleaned_data["startpage"]:
            self._errors["endpage"] = ErrorList([_(u"You must not give an end page if there is no start page.")])
            del cleaned_data["endpage"]
        if cleaned_data["reference_type"] != "GEN" and not cleaned_data["date"]:
            self._errors["date"] = ErrorList([_(u"This field is required for this reference type.")])
            del cleaned_data["date"]
        reference_types = ["ART", "ADVS", "BILL", "BOOK", "CASE", "CTLG", "COMP", "DATA", "ELEC", "HEAR",
                           "ICOMM", "MAP", "MPCT", "MUSIC", "PAMP", "PAT", "PCOMM", "RPRT", "SER",
                           "SLIDE", "SOUND", "STAT", "THES", "UNBILL", "UNPB", "VIDEO"]
        self._forbid_field("part_title", reference_types)
        self._forbid_field("part_authors", reference_types)
        if cleaned_data["reference_type"] in ["ABST", "INPR", "JOUR", "JFULL", "MGZN", "NEWS"] \
                and not cleaned_data["publication_title"]:
            self._errors["publication_title"] = ErrorList([_(u"This field is required for this reference type.")])
            del cleaned_data["publication_title"]
        self._forbid_field("volume", ["ART", "CTLG", "COMP", "INPR", "ICOMM", "MAP", "MPCT", "PAMP", "PCOMM", "SLIDE",
                                      "SOUND", "UNPB", "VIDEO"])
        self._forbid_field("issue", ["ART", "ADVS", "BILL", "BOOK", "CONF", "ELEC", "HEAR", "ICOMM",
                                     "MPCT", "MUSIC", "PAMP", "PCOMM", "RPRT", "SER", "SLIDE", "SOUND", "STAT",
                                     "UNBILL", "UNPB", "VIDEO"])
        self._forbid_field("startpage", ["ART", "CTLG", "COMP", "HEAR", "INPR", "ICOMM", "MAP", "MPCT",
                                         "MUSIC", "PAMP", "PCOMM", "SLIDE", "SOUND", "THES", "UNBILL", "UNPB", "VIDEO"])
        self._forbid_field("endpage", ["ART", "CTLG", "COMP", "HEAR", "INPR", "ICOMM", "MAP", "MPCT",
                                       "MUSIC", "PAMP", "PCOMM", "SLIDE", "SOUND", "UNBILL", "UNPB", "VIDEO"])
        self._forbid_field("publisher", ["BILL", "ICOMM", "PAT", "PCOMM", "SLIDE", "STAT", "UNBILL", "UNPB"])
        self._forbid_field("city", ["BILL", "ELEC", "HEAR", "ICOMM", "PCOMM", "SLIDE", "STAT", "UNBILL", "UNPB"])
        return cleaned_data

    def get_reference(self):
        u"""Creates a new reference object and puts all user input into it.  In
        case of editing an existing reference, this method makes a deep copy of
        the extisting reference instance and modifies it accoring to what the
        user changed.  And in case of creating a new reference, it creates a
        new reference object from the user's input.

        Nothing is actually saved to the database here.  This is a helper
        routine, exclusively used in `save`.

        :Return:
          a new reference object, containing all user input

        :rtype: ``pyrefdb.Reference``
        """
        if self.reference:
            reference = copy.deepcopy(self.reference)
        else:
            reference = pyrefdb.Reference()
            reference.extended_data = utils.ExtendedData()
            reference.creator = self.user.pk
        reference.type = self.cleaned_data["reference_type"]
        if self.cleaned_data["part_title"] or self.cleaned_data["part_authors"]:
            if not reference.part:
                reference.part = pyrefdb.Part()
            reference.part.title = self.cleaned_data["part_title"]
            reference.part.authors = self.cleaned_data["part_authors"]
        if not reference.publication:
            reference.publication = pyrefdb.Publication()
        reference.publication.title = self.cleaned_data["publication_title"]
        reference.publication.authors = self.cleaned_data["publication_authors"]
        lib_info = reference.get_or_create_lib_info(utils.refdb_username(self.user.id))
        lib_info.notes = self.cleaned_data["private_notes"]
        lib_info.reprint_status = "INFILE" if self.cleaned_data["private_reprint_available"] else "NOTINFILE"
        lib_info.availability = self.cleaned_data["private_reprint_location"]
        if not reference.publication.pub_info:
            reference.publication.pub_info = pyrefdb.PubInfo()
        pub_info = reference.publication.pub_info
        pub_info.pub_date = self.cleaned_data["date"]
        reference.relevance = self.cleaned_data["relevance"]
        pub_info.volume = self.cleaned_data["volume"]
        pub_info.issue = self.cleaned_data["issue"]
        pub_info.startpage = self.cleaned_data["startpage"]
        pub_info.endpage = self.cleaned_data["endpage"]
        pub_info.publisher = self.cleaned_data["publisher"]
        pub_info.city = self.cleaned_data["city"]
        pub_info.address = self.cleaned_data["address"]
        pub_info.serial = self.cleaned_data["serial"]
        pub_info.links["doi"] = self.cleaned_data["doi"]
        pub_info.links["url"] = self.cleaned_data["weblink"]
        if self.cleaned_data["global_notes"] and not reference.comments:
            reference.comments = pyrefdb.XNote()
        if reference.comments:
            reference.comments.set_text_content(self.cleaned_data["global_notes"])
        reference.institute_publication = self.cleaned_data["institute_publication"]
        reference.groups = set(group.id for group in self.cleaned_data["groups"])
        if self.cleaned_data["has_reprint"]:
            reference.users_with_offprint.keywords.add(self.user.pk)
        else:
            reference.users_with_offprint.keywords.discard(self.user.pk)
        reference.abstract = self.cleaned_data["abstract"]
        reference.keywords = self.cleaned_data["keywords"]
        reference.freeze()
        return reference

    def save_lists(self, reference):
        u"""Stores the new personal references lists that the user selected in
        the RefDB database.  It does so by comparing the new lists with the old
        lists and dumping or picking the changed items.

        :Parameters:
          - `reference`: the reference that should be added to or removed from
            the lists

        :type reference: ``pyrefdb.Reference``
        """
        # FixMe: This method could be made more efficient with sets.
        for list_ in self.cleaned_data["lists"]:
            if list_ not in self.old_lists:
                listname = list_.partition("-")[2] or None
                self.refdb_rollback_actions.append(utils.DumprefRollback(self.user, reference.id, listname))
                utils.get_refdb_connection(self.user).pick_references([reference.id], listname)
                
        for list_ in self.old_lists:
            if list_ not in self.cleaned_data["lists"]:
                listname = list_.partition("-")[2]
                self.refdb_rollback_actions.append(utils.PickrefRollback(self.user, reference.id, listname))
                utils.get_refdb_connection(self.user).dump_references([reference.id], listname or None)

    def _save_extended_note(self, extended_note, citation_key):
        u"""Stores an extended note in the RefDB database.  This is used as a
        helper method in `save`.

        :Parameters:
          - `extended_note`: The extrended note to be stored.  If ``None`` or
            ``False``, this method is a no-op.  Note that this method
            distinguishs between newly created and updated extended notes by
            the extistence of a citation key in the note.
          - `citation_key`: Extended note citatation key to be used if the
            extended note is new (i.e. not yet in the RefDB database).
            However, it means no harm to give this parameter always.
        """
        if extended_note:
            if extended_note.citation_key:
                self.refdb_rollback_actions.append(utils.UpdatenoteRollback(self.user, extended_note))
                utils.get_refdb_connection(self.user).update_extended_notes(extended_note)
            else:
                extended_note.citation_key = "django-refdb-comments-" + citation_key
                utils.get_refdb_connection(self.user).add_extended_notes(extended_note)
                self.refdb_rollback_actions.append(utils.DeletenoteRollback(self.user, extended_note))

    def _update_last_modification(self, new_reference):
        # FixMe: As long as RefDB's addref doesn't return the IDs of the added
        # references, I can't have the "id" attribute set in ``new_reference``
        # in case of a newly added reference.  See
        # https://sourceforge.net/tracker/?func=detail&aid=2805372&group_id=26091&atid=385994
        # for further information.  So I have to re-fetch the reference in this
        # case.  Fortunately, it isn't a frequent case.
        id_ = new_reference.id
        if id_ is None:
            id_ = utils.get_refdb_connection(self.user).get_references(":CK:=" + new_reference.citation_key)[0].id
        django_object, created = models.Reference.objects.get_or_create(reference_id=id_)
        if not created:
            django_object.mark_modified()
            django_object.save()

    def save(self):
        u"""Stores the currently edited reference in the database, and saves
        the possibly uploaded PDF file in the appropriate place.  Moreover, if
        the changes in the reference also affect the file name of the PDF, it
        renames the PDFs accordingly.  And finally, it updates the „last
        modified“ fields in the Django models so that the caching framework can
        work efficiently and properly.
        """
        new_reference = self.get_reference()
        if self.reference:
            self.refdb_rollback_actions.append(utils.UpdaterefRollback(self.user, self.reference))
            utils.get_refdb_connection(self.user).update_references(new_reference)
        else:
            citation_key = utils.get_refdb_connection(self.user).add_references(new_reference)[0][0]
            self.refdb_rollback_actions.append(utils.DeleterefRollback(self.user, citation_key))
            new_reference.citation_key = citation_key

        self._save_extended_note(new_reference.comments, "django-refdb-comments-" + citation_key)
        self._save_extended_note(new_reference.users_with_offprint, "django-refdb-users-with-offprint-" + citation_key)

        self.save_lists(new_reference)
        if self.reference and utils.slugify_reference(new_reference) != utils.slugify_reference(self.reference):
            if self.reference.global_pdf_available:
                shutil.move(pdf_filepath(self.reference), pdf_filepath(new_reference))
            for user_id in self.reference.pdf_is_private:
                if self.reference.pdf_is_private[user_id]:
                    shutil.move(pdf_filepath(self.reference, user_id), pdf_filepath(new_reference, user_id))
        pdf_file = self.cleaned_data["pdf"]
        if pdf_file:
            private = self.cleaned_data["pdf_is_private"]
            if private:
                new_reference.users_with_personal_pdf.add(self.user)
            else:
                new_reference.global_pdf_available = True
            filepath = pdf_filepath(new_reference, self.user if private else None)
            directory = os.path.dirname(filepath)
            if not os.path.exists(directory):
                os.makedirs(directory)
            destination = open(filepath, "wb+")
            for chunk in pdf_file.chunks():
                destination.write(chunk)
            destination.close()
        self._update_last_modification(new_reference)
        return new_reference


@login_required
def edit(request, citation_key):
    u"""Edits or creates a reference.

    :Parameters:
      - `request`: the current HTTP Request object
      - `citation_key`: the citation key of the reference to be edited; if
        ``None``, create a new one

    :type request: ``HttpRequest``
    :type citation_key: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if citation_key:
        connection = utils.get_refdb_connection(request.user)
        references = connection.get_references(":CK:=" + citation_key, with_extended_notes=True,
                                               extended_notes_constraints=":NCK:~^django-refdb-")
        if not references:
            raise Http404("Citation key \"%s\" not found." % citation_key)
        else:
            reference = references[0]
            reference.fetch(["groups", "global_pdf_available", "users_with_offprint", "relevance", "comments",
                             "pdf_is_private", "creator", "institute_publication"], connection, request.user.pk)
    else:
        reference = None
    if request.method == "POST":
        reference_form = ReferenceForm(request, reference, request.POST, request.FILES)
        if reference_form.is_valid():
            new_reference = reference_form.save()
            # We don't need this in the cache.  It's only needed for saving,
            # and then it has to be recalculated anyway.
            del new_reference.extended_notes
            cache.set(cache_prefix + new_reference.id, new_reference)
    else:
        reference_form = ReferenceForm(request, reference)
    title = _(u"Edit reference") if citation_key else _(u"Add reference")
    return render_to_response("edit_reference.html", {"title": title, "reference": reference_form},
                              context_instance=RequestContext(request))


cache_prefix = "refdb-reference-"
length_cache_prefix = len(cache_prefix)


@login_required
def view(request, citation_key):
    u"""Shows a reference.

    :Parameters:
      - `request`: the current HTTP Request object
      - `citation_key`: the citation key of the reference

    :type request: ``HttpRequest``
    :type citation_key: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    connection = utils.get_refdb_connection(request.user)
    references = connection.get_references(":CK:=" + citation_key, with_extended_notes=True,
                                           extended_notes_constraints=":NCK:~^django-refdb-")
    if not references:
        raise Http404("Citation key \"%s\" not found." % citation_key)
    reference = references[0]
    reference.fetch(["groups", "global_pdf_available", "users_with_offprint", "relevance", "comments",
                     "pdf_is_private", "creator", "institute_publication"], connection, request.user.pk)
    lib_info = reference.get_lib_info(utils.refdb_username(request.user.id))
    pdf_path, pdf_is_private = pdf_filepath(reference, request.user.pk, existing=True)
    return render_to_response("show_reference.html", {"title": _(u"View reference"),
                                                      "reference": reference, "lib_info": lib_info,
                                                      "pdf_path": pdf_path, "pdf_is_private": pdf_is_private},
                              context_instance=RequestContext(request))


class SearchForm(forms.Form):
    u"""Form class for the search filters.  Currently, it only accepts a RefDB
    query string.
    """

    _ = ugettext_lazy
    query_string = forms.CharField(label=_("Query string"), required=False)


@login_required
def search(request):
    u"""Searchs for references and presents the search results.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    search_form = SearchForm(request.GET)
    return render_to_response("search.html", {"title": _(u"Search"), "search": search_form},
                              context_instance=RequestContext(request))


def form_fields_to_query(form_fields):
    query_string = form_fields.get("query_string", "")
    return query_string


class CommonBulkViewData(object):

    def __init__(self, query_string, offset, limit, refdb_connection, ids):
        self.query_string, self.offset, self.limit, self.refdb_connection, self.ids = \
            query_string, offset, limit, refdb_connection, ids

    def get_all_values(self):
        return self.query_string, self.offset, self.limit, self.refdb_connection, self.ids


def get_last_modification_date(request):
    query_string = form_fields_to_query(request.GET)
    offset = request.GET.get("offset")
    limit = request.GET.get("limit")
    try:
        offset = int(offset)
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    refdb_connection = utils.get_refdb_connection(request.user)
    ids = refdb_connection.get_references(query_string, output_format="ids", offset=offset, limit=limit)
    request.common_data = CommonBulkViewData(query_string, offset, limit, refdb_connection, ids)
    return utils.last_modified(request.user, ids)

@login_required
@last_modified(get_last_modification_date)
def bulk(request):

    def build_page_link(new_offset):
        new_query_dict = request.GET.copy()
        new_query_dict["offset"] = new_offset
        new_query_dict["limit"] = limit
        return "?" + urllib.urlencode(new_query_dict) \
            if 0 <= new_offset < number_of_references and new_offset != offset else None

    query_string, offset, limit, refdb_connection, ids = request.common_data.get_all_values()
    number_of_references = refdb_connection.count_references(query_string)
    prev_link = build_page_link(offset - limit)
    next_link = build_page_link(offset + limit)
    pages = []
    for i in range(number_of_references // limit + 1):
        link = build_page_link(i * limit)
        pages.append(link)
    all_references = cache.get_many(cache_prefix + id_ for id_ in ids)
    all_references = dict((cache_id[length_cache_prefix:], reference) for cache_id, reference in all_references.iteritems())
    missing_ids = set(ids) - set(all_references)
    if missing_ids:
        missing_references = refdb_connection.get_references(u" OR ".join(":ID:=" + id_ for id_ in missing_ids))
        missing_references = dict((reference.id, reference) for reference in missing_references)
        all_references.update(missing_references)
    references = [all_references[id_] for id_ in ids]
    response = render_to_response("bulk.html", {"title": _(u"Bulk view"), "references": references,
                                                "prev_link": prev_link, "next_link": next_link, "pages": pages},
                                  context_instance=RequestContext(request))
    # I must do it here because the render_to_response call may have populated
    # some extended_data fields in the references.
    for reference in references:
        cache.set(cache_prefix + reference.id, reference)
    return response
