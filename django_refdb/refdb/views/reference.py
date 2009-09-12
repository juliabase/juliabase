#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Views for viewing, editing, adding, and searching for references.
"""

from __future__ import absolute_import

import os.path, shutil, re, copy
import pyrefdb
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseNotAllowed, HttpResponse
from django.views.decorators.http import last_modified, require_http_methods
from django.template import defaultfilters
from django.http import QueryDict
import django.core.urlresolvers
from django import forms
from django.forms.util import ValidationError, ErrorList
from django.contrib.auth.decorators import login_required
from django.utils.encoding import iri_to_uri
from django.utils.http import urlencode
from django.utils.translation import ugettext as _, ungettext, ugettext_lazy
from django.core.cache import cache
import django.contrib.auth.models
from django.conf import settings
from .. import utils, models


class HttpResponseSeeOther(HttpResponse):
    u"""Response class for HTTP 303 redirects.  Unfortunately, Django does the
    same wrong thing as most other web frameworks: it knows only one type of
    redirect, with the HTTP status code 302.  However, this is very often not
    desirable.  In Chantal, we've frequently the use case where an HTTP POST
    request was successful, and we want to redirect the user back to the main
    page, for example.

    This must be done with status code 303, and therefore, this class exists.
    It can simply be used as a drop-in replacement of HttpResponseRedirect.
    """
    status_code = 303

    def __init__(self, redirect_to):
        super(HttpResponseSeeOther, self).__init__()
        self["Location"] = iri_to_uri(redirect_to)


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
            if reference.users_with_offprint:
                initial["has_reprint"] = unicode(user.pk) in reference.users_with_offprint.keywords
            initial["abstract"] = reference.abstract or u""
            initial["keywords"] = u"; ".join(reference.keywords)
            lib_info = reference.get_lib_info(utils.refdb_username(user.id))
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
        self.fields["shelves"].choices = [(shelf.pk, unicode(shelf)) for shelf in models.Shelf.objects.all()] \
            or [(u"", 9*u"-")]

    def clean_shelves(self):
        value = self.cleaned_data["shelves"]
        if value == [u""]:
            value = []
        return models.Shelf.objects.in_bulk([int(pk) for pk in set(value)]).values()

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
        reference.shelves = set(shelf.id for shelf in self.cleaned_data["shelves"])
        if self.cleaned_data["has_reprint"] and not reference.users_with_offprint:
            reference.users_with_offprint = pyrefdb.XNote()
        if self.cleaned_data["has_reprint"]:
            reference.users_with_offprint.keywords.add(str(self.user.pk))
        elif reference.users_with_offprint:
            reference.users_with_offprint.keywords.discard(str(self.user.pk))
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
                extended_note.citation_key = citation_key
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
        # I defer the update of the extended note to after having written the
        # extended notes.  The altervative to this arguably ugly operation is
        # to avoid using the reference's citation key in the citation key of
        # the extended notes.  Instead, one would have to use a random suffix,
        # which is alos not very nice.  In particular, it would make the lookup
        # slightly slower and debugging more cumbersome.
        extended_notes = new_reference.extended_notes
        new_reference.extended_notes = None
        connection = utils.get_refdb_connection(self.user)
        if self.reference:
            self.refdb_rollback_actions.append(utils.UpdaterefRollback(self.user, self.reference))
            connection.update_references(new_reference)
        else:
            citation_key = connection.add_references(new_reference)[0][0]
            self.refdb_rollback_actions.append(utils.DeleterefRollback(self.user, citation_key))
            new_reference.citation_key = citation_key

        self._save_extended_note(new_reference.comments, "django-refdb-comments-" + new_reference.citation_key)
        self._save_extended_note(
            new_reference.users_with_offprint, "django-refdb-users-with-offprint-" + new_reference.citation_key)
        new_reference.extended_notes = extended_notes
        connection.update_note_links(new_reference)

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
        references = connection.get_references(":CK:=" + citation_key)
        if not references:
            raise Http404("Citation key \"%s\" not found." % citation_key)
        else:
            reference = references[0]
            reference.fetch(["shelves", "global_pdf_available", "users_with_offprint", "relevance", "comments",
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
    reference.fetch(["shelves", "global_pdf_available", "users_with_offprint", "relevance", "comments",
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


class SelectionBoxForm(forms.Form):
    _ = ugettext_lazy
    selected = forms.BooleanField(label=_("selected"), required=False)


output_format_choices = (
    ("", 9*u"-"),
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
    _ = ugettext_lazy
    format = forms.ChoiceField(label=_("Export as"), choices=output_format_choices, required=False)


class AddToShelfForm(forms.Form):
    _ = ugettext_lazy
    new_shelf = forms.ChoiceField(label=_("Add to shelf"), required=False)

    def __init__(self, *args, **kwargs):
        super(AddToShelfForm, self).__init__(*args, **kwargs)
        self.fields["new_shelf"].choices = \
            [("", 9*u"-")] + [(shelf.pk, unicode(shelf)) for shelf in models.Shelf.objects.all()]


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
        return "?" + urlencode(new_query_dict) if 0 <= new_offset < number_of_references and new_offset != offset else None

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
    for reference in references:
        reference.fetch(["shelves", "global_pdf_available", "users_with_offprint", "relevance", "comments",
                         "pdf_is_private", "creator", "institute_publication"], refdb_connection, request.user.pk)
        cache.set(cache_prefix + reference.id, reference)
        reference.selection_box = SelectionBoxForm(prefix=reference.id)
    export_form = ExportForm()
    add_to_shelf_form = AddToShelfForm()
    add_to_list_form = AddToListForm(request.user)
    return render_to_response("bulk.html", {"title": _(u"Bulk view"), "references": references,
                                            "prev_link": prev_link, "next_link": next_link, "pages": pages,
                                            "add_to_shelf": add_to_shelf_form, "export": export_form,
                                            "add_to_list": add_to_list_form},
                              context_instance=RequestContext(request))


class AddToListForm(forms.Form):
    _ = ugettext_lazy
    existing_list = forms.ChoiceField(label=_("List"), required=False)
    new_list = forms.CharField(label=_("New list"), max_length=255, required=False)

    def __init__(self, user, *args, **kwargs):
        super(AddToListForm, self).__init__(*args, **kwargs)
        lists = utils.get_lists(user)[0]
        self.short_listnames = set(list_[0] for list_ in lists)
        self.fields["existing_list"].choices = [("", 9*"-")] + lists
        self.optional = True

    def clean(self):
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


def add_references_to_list(ids, add_to_list_form, user):
    # add_to_list_form must be bound and valid
    if add_to_list_form.cleaned_data["existing_list"]:
        listname = add_to_list_form.cleaned_data["existing_list"]
    else:
        verbose_name = add_to_list_form.cleaned_data["new_list"]
        listname = defaultfilters.slugify(verbose_name)
    connection = utils.get_refdb_connection(user)
    reference_id = connection.get_references(":CK:=" + citation_key, output_format="ids")[0]
    connection.pick_references(ids, listname)
    if add_to_list_form.cleaned_data["new_list"]:
        extended_note = connection.get_extended_notes(":NCK:=%s-%s" % (utils.refdb_username(user.id), listname))[0]
        extended_note.set_text_content(verbose_name)
        connection.update_extended_notes(extended_note)


@login_required
@require_http_methods(["POST"])
def add_to_list(request, citation_key):
    # This is not used currently.  I may become an API view.
    add_to_list_form = AddToListForm(request.user, request.POST)
    add_to_list_form.optional = False
    if add_to_list_form.is_valid():
        add_references_to_list([reference_id], add_to_list_form, request.user)
        next_url = django.core.urlresolvers.reverse(view, kwargs=dict(citation_key=citation_key))
        return utils.HttpResponseSeeOther(next_url)
    # With an unmanipulated browser, you never get this far
    return render_to_response("add_to_list.html", {"title": _(u"Add to references list"), "add_to_list": add_to_list_form},
                              context_instance=RequestContext(request))


output_format_meta_info = {
    "ris": ("text/plain", ".ris"),
    "html": ("text/html", ".html"),
    "xhtml": ("application/xhtml+xml", ".xhtml"),
    "db31": ("text/plain", ".dbk"),
    "db31x": ("text/plain", ".dbk"),
    "db50": ("text/plain", ".dbk"),
    "db50x": ("text/plain", ".dbk"),
    "teix": ("text/xml", ".xml"),
    "tei5x": ("text/xml", ".xml"),
    "mods": ("text/xml", ".mods"),
    "bibtex": ("text/plain", ".bib"),
    "rtf": ("text/rtf", ".rtf")
    }

@login_required
@require_http_methods(["GET"])
def export(request):
    format = request.GET.get("format")
    try:
        content_type, file_extension = output_format_meta_info[format]
    except KeyError:
        error_string = _(u"No format given.") if not format else _(u"Format “%s” is unknown.") % format
        raise Http404(error_string)
    ids = set()
    for key, value in request.GET.iteritems():
        if key.endswith("-selected") and value == "on":
            ids.add(key.partition("-")[0])
    output = utils.get_refdb_connection(request.user).get_references(u" OR ".join(":ID:=" + id_ for id_ in ids),
                                                                     output_format=format)
    response = HttpResponse(content_type=content_type + "; charset=utf-8")
    response['Content-Disposition'] = "attachment; filename=references" + file_extension
    response.write(output)
    return response


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


def is_referentially_valid(export_form, add_to_shelf_form, add_to_list_form, selection_box_forms, global_dummy_form):
    referentially_valid = True
    action = None
    actions = []
    if export_form.is_valid() and export_form.cleaned_data["format"]:
        actions.append("export")
    if add_to_shelf_form.is_valid() and add_to_shelf_form.cleaned_data["new_shelf"]:
        actions.append("shelf")
    if add_to_list_form.is_valid() and (
        add_to_list_form.cleaned_data["existing_list"] or add_to_list_form.cleaned_data["new_list"]):
        actions.append("list")
    if not actions:
        append_error(global_dummy_form, _(u"You must select an action."))
        referentially_valid = False
    elif len(actions) > 1:
        append_error(global_dummy_form, _(u"You can't do more that one thing at the same time."))
        referentially_valid = False
    else:
        action = actions[0]
    return referentially_valid, action


@login_required
@require_http_methods(["POST"])
def dispatch(request):
    export_form = ExportForm(request.POST)
    add_to_shelf_form = AddToShelfForm(request.POST)
    add_to_list_form = AddToListForm(request.user, request.POST)
    global_dummy_form = forms.Form(request.POST)
    ids = set()
    for key, value in request.POST.iteritems():
        id_, dash, name = key.partition("-")
        if name == "selected" and value == "on":
            ids.add(id_)
    selection_box_forms = [SelectionBoxForm(request.POST, prefix=id_) for id_ in ids]
    if not selection_box_forms:
        return render_to_response("nothing_selected.html", {"title": _(u"Nothing selected")},
                                  context_instance=RequestContext(request))
    all_valid = export_form.is_valid() and add_to_shelf_form.is_valid() and add_to_list_form.is_valid()
    all_valid = all([form.is_valid() for form in selection_box_forms]) and all_valid
    referentially_valid, action = is_referentially_valid(export_form, add_to_shelf_form, add_to_list_form,
                                                         selection_box_forms, global_dummy_form)
    if all_valid and referentially_valid:
        if action == "export":
            query_dict = {"format": export_form.cleaned_data["format"]}
            query_dict.update((id_ + "-selected", "on") for id_ in ids)
            query_string = urlencode(query_dict)
            return HttpResponseSeeOther(django.core.urlresolvers.reverse(export) + "?" + query_string)
        elif action == "shelf":
            # FixMe: This must be changed from using citation keys to using
            # IDs.  However, first
            # https://sourceforge.net/tracker/?func=detail&aid=2857792&group_id=26091&atid=385991
            # needs to be fixed.
            citation_keys = [reference.citation_key for reference in utils.get_refdb_connection(request.user).
                             get_references(" OR ".join(":ID:=" + id_ for id_ in ids))]
            utils.get_refdb_connection(request.user).add_note_links(
                ":NCK:=django-refdb-shelf-" + add_to_shelf_form.cleaned_data["new_shelf"],
                u" ".join(":CK:=" + citation_key for citation_key in citation_keys))
        elif action == "list":
            add_references_to_list(ids, add_to_list_form, request.user)
    return render_to_response("dispatch.html", {"title": _(u"Action dispatch"), "export": export_form,
                                                "add_to_shelf": add_to_shelf_form, "add_to_list": add_to_list_form,
                                                "global_dummy": global_dummy_form, "selection_boxes": selection_box_forms},
                              context_instance=RequestContext(request))
