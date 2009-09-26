#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions for the views.
"""

from __future__ import absolute_import

import pyrefdb
from django.http import HttpResponse
from django.utils.encoding import iri_to_uri
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from .. import models


# FixMe: This class is code duplication to Chantal

class HttpResponseSeeOther(HttpResponse):
    u"""Response class for HTTP 303 redirects.  Unfortunately, Django does the
    same wrong thing as most other web frameworks: it knows only one type of
    redirect, with the HTTP status code 302.  However, this is very often not
    desirable.  In Django-RefDB, we've frequently the use case where an HTTP
    POST request was successful, and we want to redirect the user back to the
    main page, for example.

    This must be done with status code 303, and therefore, this class exists.
    It can simply be used as a drop-in replacement of HttpResponseRedirect.
    """
    status_code = 303

    def __init__(self, redirect_to):
        super(HttpResponseSeeOther, self).__init__()
        self["Location"] = iri_to_uri(redirect_to)


def slugify_reference(reference):
    u"""Converts a reference to a filename for e.g. the PDF file.  This routine
    takes the main attributes of a reference (authors, title, year) and creates
    a Unicode string from them which can be used in e.g. a filename.

    :Parameters:
      - `reference`: the reference

    :type reference: ``pyrefdb.Reference``

    :Return:
      The filename-proof name of the reference.  It contains no whitespace, is
      shortened if necessary, and has the form ``"author--year--title"``.  Note
      that it is not ASCII-only, so use it exclusively on Unicode-proof
      filesystems.

    rtype: unicode
    """
    if reference.part and reference.part.authors:
        authors = reference.part.authors
    else:
        authors = reference.publication.authors
    author = authors[0] if authors else None
    name = (author.lastname or author.name) if author else u""
    if len(authors) > 1:
        name += u" et al"
    name = name.replace(" ", "_")
    if reference.part and reference.part.title:
        title = reference.part.title
    else:
        title = reference.publication.title or u""
    try:
        year = reference.publication.pub_info.pub_date.year
        year = unicode(year) if year is not None else u""
    except AttributeError:
        year = u""
    title = title.replace(" ", "_")
    return u"%s--%s--%s" % (slugify(name), slugify(year), slugify(title[:50]))


reference_types = {
    "ABST": _(u"abstract reference"),
    "ADVS": _(u"audiovisual material"),
    "ART": _(u"art work"),
    "BILL": _(u"bill/resolution"),
    "BOOK": _(u"whole book reference"),
    "CASE": _(u"case"),
    "CHAP": _(u"book chapter reference"),
    "COMP": _(u"computer program"),
    "CONF": _(u"conference proceeding"),
    "CTLG": _(u"catalog"),
    "DATA": _(u"data file"),
    "ELEC": _(u"electronic citation"),
    "GEN": _(u"generic"),
    "ICOMM": _(u"internet communication"),
    "INPR": _(u"in press reference"),
    "JFULL": _(u"journal – full"),
    "JOUR": _(u"journal reference"),
    "MAP": _(u"map"),
    "MGZN": _(u"magazine article"),
    "MPCT": _(u"motion picture"),
    "MUSIC": _(u"music score"),
    "NEWS": _(u"newspaper"),
    "PAMP": _(u"pamphlet"),
    "PAT": _(u"patent"),
    "PCOMM": _(u"personal communication"),
    "RPRT": _(u"report"),
    "SER": _(u"serial – book, monograph"),
    "SLIDE": _(u"slide"),
    "SOUND": _(u"sound recording"),
    "STAT": _(u"statute"),
    "THES": _(u"thesis/dissertation"),
    "UNBILL": _(u"unenacted bill/resolution"),
    "UNPB": _(u"unpublished work reference"),
    "VIDEO": _(u"video recording")}
u"""dictionary mapping all RIS reference type short forms to long descriptive
names.
"""


def last_modified(user, references):
    u"""Calculates the timestamp of last modification for a given set of
    references.  It is important to see that the last modification is
    calculated “seen” from a given user.  For example, it user A has modified
    his personal notes for a given reference, this is a modification with
    respect to him.  It is *not* a modification with respect to user B because
    his personal notes about the reference haven't changed.

    :Parameters:
      - `user`: current user
      - `references`: references for which the last modification should be
        calculated

    :type user: ``django.contrib.auth.models.User``
    :type references: list of `models.Reference`

    :Return:
      the timestamp of last modification of the given references, with respect
      to the given user

    :rtype: ``datetime.datetime``
    """
    if not isinstance(references, (list, tuple)):
        references = [references]
    timestamps = []
    for reference in references:
        try:
            id_ = reference.id
        except AttributeError:
            id_ = reference
        django_reference, __ = models.Reference.objects.get_or_create(reference_id=id_)
        timestamps.append(django_reference.get_last_modification(user))
    return max(timestamps) if timestamps else None


def fetch(self, attribute_names, connection, user_id):
    u"""Fetches the extended attributes for the reference.  This method assures
    that the given attributes exist in the reference instance.  If one of them
    doesn't exist, it is filled with the current value from RefDB.

    “Extended atrribute” means that it is not a standard field of RefDB but
    realised through so-called extended notes.  Since reading of extended notes
    is a costly operation, it is done only if necessary.

    Note that this method does not guarantee that the extended attribute have
    current values.  Other code outside this method must assure that the
    contents of extended attributes is kept up-to-date.

    It is very important to see that this is a *method* in the
    `pyrefdb.Connection` class.  It is injected into that class (aka monkey
    patching).

    :Parameters:
      - `attribute_names`: the names of the extended attributes that should be
        fetched from RefDB if they don't exist yet in the reference.
      - `connection`: the connection instance to RefDB
      - `user_id`: the ID of the user who wants to retrieve the reference

    :type attribute_names: list of str
    :type connection: `pyrefdb.Connection`
    :type user_id: int
    """

    # This routine could be optimised further by splitting it into two phases:
    # fetch1 just looks which extended notes citation keys are needed and
    # returns them.  The caller collects them and does *one* RefDB call for all
    # extended notes.  The result is used to create a data structure which
    # collects the extended notes that belong to a certain reference ID.  These
    # are passed to fetch2, which generates the extended attributes from them.
    #
    # However, this makes the code much more complicated, and it makes only
    # sense if very many references are shown in the bulk view at the same
    # time.
    
    def necessary(attribute_name):
        u"""Sees whether it is necessary to fetch data for the given extended
        attribute.  It checks a) whether the attribute was requested by the
        caller of the ``fetch`` method, and checks b) whether the attribute has
        been fetched already.

        :Parameters:
          - `attribute_name`: name of the extended attribute; this name is an
            internal label only used for the context of extended notes fetching

        :type attribute_name: str

        :Return:
          whether the
        """
        if attribute_name in attribute_names:
            if attribute_name == "pdf_is_private":
                return user_id not in self.pdf_is_private
            else:
                return getattr(self, attribute_name) is None
        else:
            return False

    # ``None`` means “not yet fetched”.  Everything else, in particular
    # ``False``, means “fetched”.  The exception is ``pdf_is_private``.  Here,
    # an entry for a yet un-fetched user simply doesn't exist in the
    # dictionary.
    if not hasattr(self, "shelves"):
        self.shelves = None                 # is a set of integers
        self.global_pdf_available = None    # is a boolean
        self.users_with_offprint = None     # is an extended note
        self.relevance = None               # is an integer
        self.comments = None                # is an extended note
        self.pdf_is_private = {}
        self.creator = None                 # is an integer
        self.institute_publication = None   # is a boolean
    needed_notes_cks = {"shelves": ":NCK:~^django-refdb-shelf-",
                        "global_pdf_available": ":NCK:=django-refdb-global-pdfs",
                        "users_with_offprint": ":NCK:=django-refdb-users-with-offprint-" + self.citation_key,
                        "relevance": ":NCK:~^django-refdb-relevance-",
                        "comments": ":NCK:=django-refdb-comments-" + self.citation_key,
                        "pdf_is_private": ":NCK:=django-refdb-personal-pdfs-%d" % user_id,
                        "creator": ":NCK:~^django-refdb-creator-",
                        "institute_publication": ":NCK:=django-refdb-institute-publication"}
    query_string_components = []
    for name, needed_cks in needed_notes_cks.iteritems():
        if necessary(name):
            query_string_components.append(needed_cks)
    if query_string_components:
        notes = connection.get_extended_notes(":ID:=%s AND (%s)" % (self.id, " OR ".join(query_string_components)))
        notes = dict((note.citation_key, note) for note in notes)
        self._saved_extended_notes_cks |= set(notes)
        if necessary("shelves"):
            prefix = "django-refdb-shelf-"
            prefix_length = len(prefix)
            self.shelves = \
                set(int(citation_key[prefix_length:]) for citation_key in notes if citation_key.startswith(prefix))
        if necessary("global_pdf_available"):
            self.global_pdf_available = "django-refdb-global-pdfs" in notes
        if necessary("users_with_offprint"):
            self.users_with_offprint = notes.get("django-refdb-users-with-offprint-" + self.citation_key, False)
        if necessary("relevance"):
            prefix = "django-refdb-relevance-"
            citation_keys = [citation_key for citation_key in notes if citation_key.startswith(prefix)]
            assert 0 <= len(citation_keys) <= 1
            self.relevance = int(citation_keys[0][len(prefix):]) if citation_keys else False
        if necessary("comments"):
            self.comments = notes.get("django-refdb-comments-" + self.citation_key, False)
        if necessary("pdf_is_private"):
            self.pdf_is_private[user_id] = "django-refdb-personal-pdfs-%d" % user_id in notes
        if necessary("creator"):
            prefix = "django-refdb-creator-"
            citation_keys = [citation_key for citation_key in notes if citation_key.startswith(prefix)]
            assert 0 <= len(citation_keys) <= 1
            self.creator = int(citation_keys[0][len(prefix):]) if citation_keys else False
        if necessary("institute_publication"):
            self.institute_publication = "django-refdb-institute-publication" in notes

pyrefdb.Reference.fetch = fetch


def freeze(self):
    u"""Creates extended notes from all set extended attributes.  This method
    fills the ``extended_notes`` attribute by looking at the values of the
    extended attributes (remember that they were generated from extended
    notes).  It must be called just before saving the object to RefDB.  (It is
    superfluous to call the method when writing the object to the cache.)

    It is very important to see that this is a *method* if the
    `pyrefdb.Connection` class.  It is injected into that class (aka monkey
    patching).

    Note that this method does not save the extended notes themselves.  It just
    prepares the object so that the *links* to extended notes are updated.  In
    most cases, this is enough.  However, for global comments and “users with
    offprints”, there is a one-to-one relationship with an extended note which
    must be created and saved separately.
    """
    self.extended_notes = pyrefdb.XNoteList()
    self.extended_notes.extend("django-refdb-shelf-%d" % shelf for shelf in self.shelves)
    if self.global_pdf_available:
        self.extended_notes.append("django-refdb-global-pdfs")
    if self.users_with_offprint:
        self.extended_notes.append(self.users_with_offprint)
    if self.relevance:
        self.extended_notes.append("django-refdb-relevance-%d" % self.relevance)
    if self.comments:
        self.extended_notes.append(self.comments)
    self.extended_notes.extend("django-refdb-personal-pdfs-%s" % user_id
                               for user_id, pdf_is_private in self.pdf_is_private.iteritems() if pdf_is_private)
    if self.creator:
        self.extended_notes.append("django-refdb-creator-%d" % self.creator)
    if self.institute_publication:
        self.extended_notes.append("django-refdb-institute-publication")

pyrefdb.Reference.freeze = freeze


labels = {
    u"SOUND": {u"publication_authors": _(u"Major contributors"), u"date": _(u"Release date"),
               u"publication_title": _(u"Title"), u"city": _(u"Publication place"), u"publisher": _(u"Publisher")},
    u"STAT": {u"publication_authors": _(u"Serial"), u"endpage": _(u"End page"), u"publication_title": _(u"Act title"),
              u"volume": _(u"Title/code number"), u"startpage": _(u"Start page"), u"date": _(u"Publication date"),
              u"pages": _(u"Pages")},
    u"PAT": {u"publication_authors": _(u"Authors"), u"city": _(u"State/country"), u"endpage": _(u"End page"),
             u"publication_title": _(u"Title"), u"volume": _(u"Application number"), u"startpage": _(u"Start page"),
             u"date": _(u"Date issued"), u"issue": _(u"Patent number"), u"pages": _(u"Pages")},
    u"PAMP": {u"publication_authors": _(u"Authors"), u"date": _(u"Publication date"), u"publication_title": _(u"Title"),
              u"city": _(u"Publication place"), u"publisher": _(u"Publisher")},
    u"CHAP": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Chapter title"),
              u"endpage": _(u"End page"), u"city": _(u"City"), u"publication_title": _(u"Book title"),
              u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Authors"),
              u"date": _(u"Publication date"), u"issue": _(u"Chapter number"), u"pages": _(u"Pages")},
    u"CONF": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
              u"endpage": _(u"End page"), u"city": _(u"Publication place"), u"publication_title": _(u"Conference title"),
              u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Authors"),
              u"date": _(u"Publication date"), u"pages": _(u"Pages")},
    u"JFULL": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
               u"endpage": _(u"End page"), u"city": _(u"Publication place"), u"publication_title": _(u"Journal"),
               u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Authors"),
               u"date": _(u"Publication date"), u"issue": _(u"Issue"), u"pages": _(u"Pages")},
    u"NEWS": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
              u"endpage": _(u"End page"), u"city": _(u"City"), u"publication_title": _(u"Newspaper"),
              u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Reporters"),
              u"date": _(u"Publication date"), u"issue": _(u"Issue"), u"pages": _(u"Pages")},
    u"DATA": {u"publication_authors": _(u"Authors"), u"publisher": _(u"Publisher"), u"endpage": _(u"End location"),
              u"city": _(u"Publication place"), u"publication_title": _(u"Title"), u"volume": _(u"Volume"),
              u"startpage": _(u"Start location"), u"date": _(u"Publication date"), u"issue": _(u"Version"),
              u"pages": _(u"Location")},
    u"ABST": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
              u"endpage": _(u"End page"), u"city": _(u"Publication place"), u"publication_title": _(u"Journal"),
              u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Authors"),
              u"date": _(u"Publication date"), u"issue": _(u"Issue"), u"pages": _(u"Pages")},
    u"ELEC": {u"publication_authors": _(u"Authors"), u"publisher": _(u"Publisher"), u"endpage": _(u"End page"),
              u"publication_title": _(u"Title"), u"volume": _(u"Volume"), u"startpage": _(u"Start page"),
              u"date": _(u"Last update"), u"pages": _(u"Pages")},
    u"JOUR": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
              u"endpage": _(u"End page"), u"city": _(u"Publication place"), u"publication_title": _(u"Journal"),
              u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Authors"),
              u"date": _(u"Publication date"), u"issue": _(u"Issue"), u"pages": _(u"Pages")},
    u"PCOMM": {u"publication_authors": _(u"Authors"), u"date": _(u"Date sent"), u"publication_title": _(u"Title")},
    u"THES": {u"publication_authors": _(u"Serial"), u"publisher": _(u"Institution"), u"endpage": _(u"End page"),
              u"city": _(u"Publication place"), u"publication_title": _(u"Title"), u"volume": _(u"Volume"),
              u"date": _(u"Publication date"), u"issue": _(u"Issue")},
    u"UNBILL": {u"publication_authors": _(u"Serial"), u"date": _(u"Date of code"), u"publication_title": _(u"Act title"),
                u"volume": _(u"Bill/resolution number")},
    u"RPRT": {u"publication_authors": _(u"Authors"), u"publisher": _(u"Publisher"), u"endpage": _(u"End page"),
              u"city": _(u"Publication place"), u"publication_title": _(u"Title"), u"volume": _(u"Report number"),
              u"startpage": _(u"Start page"), u"date": _(u"Publication date"), u"pages": _(u"Pages")},
    u"VIDEO": {u"publication_authors": _(u"Major contributors"), u"date": _(u"Release date"),
               u"publication_title": _(u"Title"), u"city": _(u"Publication place"), u"publisher": _(u"Publisher")},
    u"GEN": {u"publication_authors": _(u"Secondary authors"), u"publisher": _(u"Publisher"),
             u"part_title": _(u"Primary title"), u"endpage": _(u"End page"), u"city": _(u"Publication place"),
             u"publication_title": _(u"Title, secondary"), u"volume": _(u"Volume"), u"startpage": _(u"Start page"),
             u"part_authors": _(u"Primary authors"), u"date": _(u"Primary date"), u"issue": _(u"Issue"),
             u"pages": _(u"Pages")},
    u"ICOMM": {u"publication_authors": _(u"Sender"), u"date": _(u"Date of message"), u"publication_title": _(u"Subject")},
    u"CASE": {u"publication_authors": _(u"Counsel"), u"publisher": _(u"Court"), u"endpage": _(u"End page"),
              u"city": _(u"City"), u"publication_title": _(u"Case name"), u"startpage": _(u"Start page"),
              u"date": _(u"Filed"), u"issue": _(u"Reporter number"), u"pages": _(u"Pages")},
    u"COMP": {u"publication_authors": _(u"Authors"), u"city": _(u"Publication place"), u"publisher": _(u"Publisher"),
              u"publication_title": _(u"Title"), u"date": _(u"Release date"), u"issue": _(u"Version")},
    u"UNPB": {u"publication_authors": _(u"Serial"), u"date": _(u"Publication date"), u"publication_title": _(u"Title")},
    u"CTLG": {u"publication_authors": _(u"Authors"), u"city": _(u"Publication place"), u"publisher": _(u"Publisher"),
              u"publication_title": _(u"Title"), u"date": _(u"Publication date"), u"issue": _(u"Catalog number")},
    u"MUSIC": {u"publication_authors": _(u"Composers"), u"publisher": _(u"Publisher"), u"city": _(u"Publication place"),
               u"publication_title": _(u"Title"), u"volume": _(u"Volume"), u"date": _(u"Publication date")},
    u"MGZN": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
              u"endpage": _(u"End page"), u"city": _(u"Publication place"), u"publication_title": _(u"Magazine"),
              u"volume": _(u"Volume"), u"startpage": _(u"Start page"), u"part_authors": _(u"Authors"),
              u"date": _(u"Publication date"), u"issue": _(u"Issue"), u"pages": _(u"Pages")},
    u"INPR": {u"publication_authors": _(u"Editors"), u"publisher": _(u"Publisher"), u"part_title": _(u"Title"),
              u"city": _(u"Publication place"), u"publication_title": _(u"Journal"), u"part_authors": _(u"Authors"),
              u"date": _(u"Publication date"), u"issue": _(u"Issue")},
    u"ADVS": {u"publication_authors": _(u"Authors"), u"publisher": _(u"Publisher"), u"endpage": _(u"End page"),
              u"city": _(u"Publication place"), u"publication_title": _(u"Title"), u"volume": _(u"Volume"),
              u"startpage": _(u"Start page"), u"date": _(u"Publication date"), u"pages": _(u"Pages")},
    u"SER": {u"publication_authors": _(u"Serial"), u"publisher": _(u"Publisher"), u"endpage": _(u"End page"),
             u"city": _(u"Publication place"), u"publication_title": _(u"Title"), u"volume": _(u"Volume"),
             u"startpage": _(u"Start page"), u"date": _(u"Publication date"), u"pages": _(u"Pages")},
    u"MAP": {u"publication_authors": _(u"Cartographers"), u"city": _(u"Publication place"), u"publisher": _(u"Publisher"),
             u"publication_title": _(u"Title"), u"date": _(u"Publication date"), u"issue": _(u"Map number")},
    u"MPCT": {u"publication_authors": _(u"Major contributors"), u"date": _(u"Release date"),
              u"publication_title": _(u"Title"), u"city": _(u"Publication place"), u"publisher": _(u"Studio")},
    u"ART": {u"publication_authors": _(u"Artists"), u"date": _(u"Publication date"),
             u"publication_title": _(u"Title/subject"), u"city": _(u"Publication place"), u"publisher": _(u"Publisher")},
    u"BILL": {u"publication_authors": _(u"Authors"), u"endpage": _(u"End page"), u"publication_title": _(u"Act name"),
              u"volume": _(u"Bill/resolution number"), u"startpage": _(u"Start page"), u"date": _(u"Date of code"),
              u"pages": _(u"Pages")},
    u"SLIDE": {u"publication_authors": _(u"Serial"), u"date": _(u"Publication date"), u"publication_title": _(u"Title")},
    u"BOOK": {u"publication_authors": _(u"Authors"), u"publisher": _(u"Publisher"), u"endpage": _(u"End page"),
              u"city": _(u"City"), u"publication_title": _(u"Book title"), u"volume": _(u"Volume"),
              u"startpage": _(u"Start page"), u"date": _(u"Publication date"), u"pages": _(u"Pages")},
    u"HEAR": {u"publication_authors": _(u"Authors"), u"date": _(u"Hearing date"), u"publisher": _(u"Commitee"),
              u"publication_title": _(u"Title"), u"volume": _(u"Bill number")}}


reference_types_without_part = frozenset(["ART", "ADVS", "BILL", "BOOK", "CASE", "CTLG", "COMP", "DATA", "ELEC", "HEAR",
                                          "ICOMM", "MAP", "MPCT", "MUSIC", "PAMP", "PAT", "PCOMM", "RPRT", "SER",
                                          "SLIDE", "SOUND", "STAT", "THES", "UNBILL", "UNPB", "VIDEO"])
