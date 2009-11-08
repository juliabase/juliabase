#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""Views for viewing, editing, adding, and searching for references.
"""

from __future__ import absolute_import

import os.path, re, copy, subprocess
import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponse
from django import forms
# FixMe: ErrorList must be replaced with append_error
from django.forms.util import ValidationError, ErrorList
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.core.servers.basehttp import FileWrapper
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.conf import settings
from chantal_common import utils as chantal_utils
from .. import refdb, models
from . import utils
from .rollbacks import *


def pdf_filepath(database, reference, user_id=None):
    u"""Calculates the absolute filepath of the uploaded PDF in the local
    filesystem.  If a user ID is provided, the path to the private PDF is
    returned.  If no user ID is provided, the public PDF path is returned.
    Note that this function doesn't care whether the PDF exists or not.

    :Parameters:
      - `database`: the name of the RefDB database
      - `reference`: the reference whose PDF file path should be calculated
      - `user_id`: the ID of the user who tries to retrieve their private file

    :type database: unicode
    :type reference: ``pyrefdb.Reference``, with the ``extended_data``
      attribute
    :type user_id: int

    :Return:
      the absolute path to the uploaded PDF file, no matter whether it exists
      or not

    :rtype: unicode
    """
    citation_key = reference.citation_key
    if user_id is not None:
        return os.path.join(
            "/var/lib/django_refdb_pdfs", database, citation_key, "private", str(user_id), citation_key + ".pdf")
    else:
        return os.path.join("/var/lib/django_refdb_pdfs", database, citation_key, "public", citation_key + ".pdf")


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


date_pattern = re.compile(r"(\d{4})$|(\d{4})-(\d\d?)-(\d\d?)$")
pages_pattern = re.compile(r"(.+?)(?:--(.+))?")

class ReferenceForm(forms.Form):
    u"""Form for editing and adding a reference.
    """

    _ = ugettext_lazy
    reference_type = forms.ChoiceField(label=_("Type"), choices=utils.reference_types.items())
    part_title = CharNoneField(label=_("Part title"), required=False)
    part_authors = forms.CharField(label=_("Part authors"), required=False)
    publication_title = forms.CharField(label=_("Publication title"), required=False)
    publication_title_abbrev = forms.CharField(label=_("Abbreviated publication title"), required=False)
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
    shelves = forms.MultipleChoiceField(label=_("Shelves"), required=False)
    pdf = forms.FileField(label=_(u"PDF file"), required=False)
    pdf_is_private = forms.BooleanField(label=_("PDF is private"), required=False)

    def __init__(self, request, connection, reference, *args, **kwargs):
        u"""
        :Parameters:
          - `request`: the current HTTP request
          - `connection`: connection to RefDB
          - `reference`: the reference to be edited; if ``None``, add a new one

        :type request: ``HttpRequest``
        :type connection: ``pyrefdb.Connection``
        :type reference: ``pyrefdb.Reference`` or ``NoneType``
        """
        user = request.user
        self.connection = connection
        initial = kwargs.get("initial") or {}
        lists_choices, lists_initial = refdb.get_lists(user, self.connection, reference.citation_key if reference else None)
        if reference:
            initial["reference_type"] = reference.type
            if reference.part:
                initial["part_title"] = reference.part.title
                initial["part_authors"] = serialize_authors(reference.part.authors)
            initial["publication_title"] = reference.publication.title
            initial["publication_title_abbrev"] = reference.publication.title_abbrev
            initial["publication_authors"] = serialize_authors(reference.publication.authors)
            pub_info = reference.publication.pub_info
            if pub_info:
                initial["date"] = unicode(pub_info.pub_date or u"")
                initial["volume"] = pub_info.volume or u""
                initial["issue"] = pub_info.issue or u""
                initial["startpage"] = pub_info.startpage or u""
                initial["endpage"] = pub_info.endpage or u""
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
            if reference.users_with_offprint:
                initial["has_reprint"] = unicode(user.id) in reference.users_with_offprint.keywords
            initial["abstract"] = reference.abstract or u""
            initial["keywords"] = u"; ".join(reference.keywords)
            lib_info = reference.get_lib_info(refdb.get_username(user.id))
            if lib_info:
                initial["private_notes"] = lib_info.notes or u""
                initial["private_reprint_available"] = lib_info.reprint_status == "INFILE"
                initial["private_reprint_location"] = lib_info.availability or u""
            initial["lists"] = lists_initial
            initial["shelves"] = reference.shelves
        kwargs["initial"] = initial
        super(ReferenceForm, self).__init__(*args, **kwargs)
        self.user = user
        self.reference = reference
        self.refdb_rollback_actions = request.refdb_rollback_actions
        self.fields["lists"].choices = lists_choices
        self.old_lists = lists_initial
        self.fields["shelves"].choices = refdb.get_shelves(connection) or [(u"", 9*u"-")]

    def _split_on_semicolon(self, fieldname):
        u"""Splits the content of a character field at all semicolons.  The
        returned list is empty if the field was empty.

        :Parameters:
          - `fieldname`: name of the form field

        :type fieldname: str

        :Return:
          all components of the field

        :rtype: list of unicode
        """
        return filter(None, [item.strip() for item in self.cleaned_data[fieldname].split(";")])

    def clean_part_authors(self):
        u"""Cleans the author string.  It is split at the semicolons and then
        parsed into ``Author`` instances.
        
        :Return:
          all authors

        :rtype: list of ``pyrefdb.Author``
        """
        return [pyrefdb.Author(author) for author in self._split_on_semicolon("part_authors")]

    def clean_publication_authors(self):
        u"""Cleans the author string.  It is split at the semicolons and then
        parsed into ``Author`` instances.
        
        :Return:
          all authors

        :rtype: list of ``pyrefdb.Author``
        """
        return [pyrefdb.Author(author) for author in self._split_on_semicolon("publication_authors")]

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
        return self._split_on_semicolon("keywords")

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
        if cleaned_data["reference_type"] != "GEN" and "date" in cleaned_data and not cleaned_data["date"]:
            chantal_utils.append_error(self, _(u"This field is required for this reference type."), "date")
            del cleaned_data["date"]
        self._forbid_field("part_title", utils.reference_types_without_part)
        self._forbid_field("part_authors", utils.reference_types_without_part)
        if cleaned_data["reference_type"] in ["ABST", "INPR", "JOUR", "JFULL", "MGZN", "NEWS"] \
                and not (cleaned_data["publication_title"] or cleaned_data["publication_title_abbrev"]):
            self._errors["publication_title"] = \
                ErrorList([_(u"The publication title (or its abbreviation) is required for this reference type.")])
            del cleaned_data["publication_title"]
            del cleaned_data["publication_title_abbrev"]
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
            utils.initialize_extended_attributes(reference)
            reference.creator = self.user.id
        reference.type = self.cleaned_data["reference_type"]
        if self.cleaned_data["part_title"] or self.cleaned_data["part_authors"]:
            if not reference.part:
                reference.part = pyrefdb.Part()
            reference.part.title = self.cleaned_data["part_title"]
            reference.part.authors = self.cleaned_data["part_authors"]
        if not reference.publication:
            reference.publication = pyrefdb.Publication()
        reference.publication.title = self.cleaned_data["publication_title"]
        reference.publication.title_abbrev = self.cleaned_data["publication_title_abbrev"]
        reference.publication.authors = self.cleaned_data["publication_authors"]
        lib_info = reference.get_or_create_lib_info(refdb.get_username(self.user.id))
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
        reference.shelves = set(self.cleaned_data["shelves"])
        if self.cleaned_data["has_reprint"] and not reference.users_with_offprint:
            reference.users_with_offprint = pyrefdb.XNote()
        if self.cleaned_data["has_reprint"]:
            reference.users_with_offprint.keywords.add(str(self.user.id))
        elif reference.users_with_offprint:
            reference.users_with_offprint.keywords.discard(str(self.user.id))
        reference.abstract = self.cleaned_data["abstract"]
        reference.keywords = self.cleaned_data["keywords"]
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
        for listname in self.cleaned_data["lists"]:
            if listname not in self.old_lists:
                self.refdb_rollback_actions.append(DumprefRollback(self.connection, reference.id, listname))
                self.connection.pick_references([reference.id], listname)
                
        for listname in self.old_lists:
            if listname not in self.cleaned_data["lists"]:
                self.refdb_rollback_actions.append(PickrefRollback(self.connection, reference.id, listname))
                self.connection.dump_references([reference.id], listname)

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

        :type extended_note: ``pyrefdb.XNote``
        :type citation_key: str
        """
        if extended_note:
            if extended_note.citation_key:
                self.refdb_rollback_actions.append(UpdatenoteRollback(self.connection, extended_note))
                self.connection.update_extended_notes(extended_note)
            else:
                extended_note.citation_key = citation_key
                self.connection.add_extended_notes(extended_note)
                self.refdb_rollback_actions.append(DeletenoteRollback(self.connection, extended_note))

    def _update_last_modification(self, new_reference):
        django_object, created = models.Reference.objects.get_or_create(
            reference_id=new_reference.id, citation_key=new_reference.citation_key, database=self.connection.database)
        if not created:
            django_object.mark_modified()

    def save(self):
        u"""Stores the currently edited reference in the database, and saves
        the possibly uploaded PDF file in the appropriate place.  Moreover, if
        the changes in the reference also affect the file name of the PDF, it
        renames the PDFs accordingly.  And finally, it updates the „last
        modified“ fields in the Django models so that the caching framework can
        work efficiently and properly.
        """
        new_reference = self.get_reference()
        # I defer the update of the extended note to after having written the
        # extended notes.  The altervative to this arguably ugly operation is
        # to avoid using the reference's citation key in the citation key of
        # the extended notes.  Instead, one would have to use a random suffix,
        # which is also not very nice.  In particular, it would make the lookup
        # slightly slower and debugging more cumbersome.
        extended_notes = new_reference.extended_notes
        new_reference.extended_notes = None
        if self.reference:
            self.refdb_rollback_actions.append(UpdaterefRollback(self.connection, self.reference))
            self.connection.update_references(new_reference)
        else:
            citation_key, id_, __ = self.connection.add_references(new_reference)[0]
            self.refdb_rollback_actions.append(DeleterefRollback(self.connection, id_))
            new_reference.citation_key, new_reference.id = citation_key, id_

        self._save_extended_note(new_reference.comments, "django-refdb-comments-" + new_reference.citation_key)
        self._save_extended_note(
            new_reference.users_with_offprint, "django-refdb-users-with-offprint-" + new_reference.citation_key)
        new_reference.extended_notes = extended_notes

        self.save_lists(new_reference)
        pdf_file = self.cleaned_data["pdf"]
        if pdf_file:
            private = self.cleaned_data["pdf_is_private"]
            if private:
                new_reference.pdf_is_private[self.user.id] = True
            else:
                new_reference.pdf_is_private[self.user.id] = False
                new_reference.global_pdf_available = True
            filepath = pdf_filepath(self.connection.database, new_reference, self.user.id if private else None)
            directory = os.path.dirname(filepath)
            if not os.path.exists(directory):
                os.makedirs(directory)
            destination = open(filepath, "wb+")
            for chunk in pdf_file.chunks():
                destination.write(chunk)
            destination.close()
            utils.spawn_daemon("/usr/bin/python", settings.REFDB_PATH_TO_INDEXER,
                               "/var/lib/django_refdb_pdfs", self.connection.database,
                               new_reference.citation_key, str(self.user.id) if private else None)
        utils.freeze(new_reference)
        self.connection.update_note_links(new_reference)
        self._update_last_modification(new_reference)
        return new_reference


@login_required
def edit(request, database, citation_key):
    u"""Edits or creates a reference.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database
      - `citation_key`: the citation key of the reference to be edited; if
        ``None``, create a new one

    :type request: ``HttpRequest``
    :type database: unicode
    :type citation_key: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    connection = refdb.get_connection(request.user, database)
    if citation_key:
        references = connection.get_references(":CK:=" + citation_key)
        if not references:
            raise Http404("Citation key \"%s\" not found." % citation_key)
        else:
            reference = references[0]
            utils.fetch(reference, ["shelves", "global_pdf_available", "users_with_offprint", "relevance", "comments",
                                    "pdf_is_private", "creator", "institute_publication"], connection, request.user.id)
    else:
        reference = None
    if request.method == "POST":
        reference_form = ReferenceForm(request, connection, reference, request.POST, request.FILES)
        if reference_form.is_valid():
            new_reference = reference_form.save()
            # We don't need this in the cache.  It's only needed for saving,
            # and then it has to be recalculated anyway.
            del new_reference.extended_notes
            cache.set(settings.REFDB_CACHE_PREFIX + new_reference.id, new_reference)
            success_message = _(u"Reference “%s” successfully edited.") % citation_key if citation_key \
                else _(u"Reference “%s” successfully added.") % new_reference.citation_key
            return utils.successful_response(request, success_message, view=view,
                                             kwargs={"citation_key": new_reference.citation_key, "database": database})
    else:
        reference_form = ReferenceForm(request, connection, reference)
    title = _(u"Edit reference") if citation_key else _(u"Add reference")
    return render_to_response("refdb/edit_reference.html", {"title": title, "reference": reference_form,
                                                            "database": database},
                              context_instance=RequestContext(request))


@login_required
def view(request, database, citation_key):
    u"""Shows a reference.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database
      - `citation_key`: the citation key of the reference

    :type request: ``HttpRequest``
    :type database: unicode
    :type citation_key: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    connection = refdb.get_connection(request.user, database)
    # FixMe: Is "with_extended_notes" sensible?
    references = connection.get_references(":CK:=" + citation_key, with_extended_notes=True,
                                           extended_notes_constraints=":NCK:~^django-refdb-")
    if not references:
        raise Http404("Citation key \"%s\" not found." % citation_key)
    reference = references[0]
    utils.fetch(reference, ["shelves", "global_pdf_available", "users_with_offprint", "relevance", "comments",
                            "pdf_is_private", "creator", "institute_publication"], connection, request.user.id)
    lib_info = reference.get_lib_info(refdb.get_username(request.user.id))
    global_url, private_url = utils.pdf_file_url(reference, request.user, database)
    title = _(u"%(reference_type)s “%(citation_key)s”") % {"reference_type": utils.reference_types[reference.type],
                                                           "citation_key": citation_key}
    return render_to_response("refdb/show_reference.html",
                              {"title": title, "reference": reference, "lib_info": lib_info or pyrefdb.LibInfo(),
                               "global_url": global_url, "private_url": private_url,
                               "pdf_url": private_url or global_url,
                               "with_part": reference.type not in utils.reference_types_without_part,
                               "database": database},
                              context_instance=RequestContext(request))


@login_required
def pdf(request, database, citation_key, username):
    u"""Retrieves the PDF of a reference.

    :Parameters:
      - `request`: the current HTTP Request object
      - `database`: the name of the RefDB database
      - `citation_key`: the citation key of the reference
      - `username`: the name of the user whose private PDF should be retrieved;
        if the *global* PDF should be retrieved, this is ``None``

    :type request: ``HttpRequest``
    :type database: unicode
    :type citation_key: unicode
    :type username: unicode

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    # FixMe: Eventually, this function should use something like
    # <http://code.djangoproject.com/ticket/2131>.
    connection = refdb.get_connection(request.user, database)
    try:
        reference = connection.get_references(":CK:=" + citation_key)[0]
    except IndexError:
        raise Http404("Citation key \"%s\" not found." % citation_key)
    utils.fetch(reference, ["global_pdf_available", "pdf_is_private"], connection, request.user.id)
    if username:
        user_id = request.user.id
        if username != request.user.username:
            raise PermissionDenied()
        if not reference.pdf_is_private[user_id]:
            raise Http404("You have no private PDF for this reference.")
    else:
        user_id = None
        if not reference.global_pdf_available:
            raise Http404("No public PDF available for this reference.")
    filename = pdf_filepath(database, reference, user_id)
    wrapper = FileWrapper(open(filename, "rb"))
    response = HttpResponse(wrapper, content_type="application/pdf")
    response["Content-Length"] = os.path.getsize(filename)
    response["Content-Disposition"] = "attachment; filename=%s.pdf" % utils.slugify_reference(reference)
    return response
