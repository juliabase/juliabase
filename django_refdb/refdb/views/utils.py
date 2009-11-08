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


u"""General helper functions for the views.
"""

from __future__ import absolute_import

import sys, hashlib, os, os.path, unicodedata
import pyrefdb
from django.http import HttpResponse
from django.utils.encoding import iri_to_uri
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
import django.core.urlresolvers
from django.core.cache import cache
from django.conf import settings
from .. import models, refdb
import chantal_common


class RedirectException(Exception):

    def __init__(self, redirect_to):
        super(RedirectException, self).__init__(self)
        self.redirect_to = redirect_to


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


def last_modified(user, connection, ids):
    u"""Calculates the timestamp of last modification for a given set of
    references.  It is important to see that the last modification is
    calculated “seen” from a given user.  For example, it user A has modified
    his personal notes for a given reference, this is a modification with
    respect to him.  It is *not* a modification with respect to user B because
    his personal notes about the reference haven't changed.

    :Parameters:
      - `user`: current user
      - `connection`: connection to RefDB
      - `ids`: the IDs if the references for which the last modification should
        be calculated

    :type user: ``django.contrib.auth.models.User``
    :type connection: ``pyrefdb.Connection``
    :type references: list of str

    :Return:
      the timestamp of last modification of the given references, with respect
      to the given user

    :rtype: ``datetime.datetime``
    """
    timestamps = []
    missing_ids = []
    for id_ in ids:
        try:
            django_reference = models.Reference.objects.get(reference_id=id_)
        except models.Reference.DoesNotExist:
            missing_ids.append(id_)
        else:
            timestamps.append(django_reference.get_last_modification(user))
    if missing_ids:
        references = connection.get_references(u" OR ".join(u":ID:=" + id_ for id_ in missing_ids))
        for reference in references:
            django_reference = models.Reference.objects.create(
                reference_id=reference.id, citation_key=reference.citation_key, database=connection.database)
            timestamps.append(django_reference.get_last_modification(user))
    return max(timestamps) if timestamps else None


def initialize_extended_attributes(reference):
    u"""Initializes the extended attributes with default values.  It overwrites
    any old values that are in those attributes.  This routine should only be
    called if the extended attributes doesn't exist yet.  See ``fetch`` for
    further information.

    :Parameters:
      - `reference`: the reference whose extended attributes should be set to
        defaults

    :type reference: `pyrefdb.Reference`
    """
    # ``None`` means “not yet fetched”.  Everything else, in particular
    # ``False``, means “fetched”.  The exception is ``pdf_is_private``.  Here,
    # an entry for a yet un-fetched user simply doesn't exist in the
    # dictionary.
    reference.shelves = None                 # is a set of integers
    reference.global_pdf_available = None    # is a boolean
    reference.users_with_offprint = None     # is an extended note
    reference.relevance = None               # is an integer
    reference.comments = None                # is an extended note
    reference.pdf_is_private = {}
    reference.creator = None                 # is an integer
    reference.institute_publication = None   # is a boolean


def fetch(reference, attribute_names, connection, user_id):
    u"""Fetches the extended attributes for the reference.  This function
    assures that the given attributes exist in the reference instance.  If one
    of them doesn't exist, it is filled with the current value from RefDB.

    “Extended attribute” means that it is not a standard field of RefDB but
    realised through so-called extended notes.  Since reading of extended notes
    is a costly operation, it is done only if necessary.

    Note that this method does not guarantee that the extended attributes have
    current values.  Other code outside this method must assure that the
    contents of extended attributes is kept up-to-date.

    By the way, it is not necessary to call `initialize_extended_attributes`
    before calling this function since it does so if necessary itself.

    :Parameters:
      - `reference`: the reference whose extended attributes should be fetched
      - `attribute_names`: the names of the extended attributes that should be
        fetched from RefDB if they don't exist yet in the reference.
      - `connection`: the connection instance to RefDB
      - `user_id`: the ID of the user who wants to retrieve the reference

    :type reference: `pyrefdb.Reference`
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
                return user_id not in reference.pdf_is_private
            else:
                return getattr(reference, attribute_name) is None
        else:
            return False

    if not hasattr(reference, "shelves"):
        initialize_extended_attributes(reference)
    needed_notes_cks = {"shelves": ":NCK:~^django-refdb-shelf-",
                        "global_pdf_available": ":NCK:=django-refdb-global-pdfs",
                        "users_with_offprint": ":NCK:=django-refdb-users-with-offprint-" + reference.citation_key,
                        "relevance": ":NCK:~^django-refdb-relevance-",
                        "comments": ":NCK:=django-refdb-comments-" + reference.citation_key,
                        "pdf_is_private": ":NCK:=django-refdb-personal-pdfs-%d" % user_id,
                        "creator": ":NCK:~^django-refdb-creator-",
                        "institute_publication": ":NCK:=django-refdb-institute-publication"}
    query_string_components = []
    for name, needed_cks in needed_notes_cks.iteritems():
        if necessary(name):
            query_string_components.append(needed_cks)
    if query_string_components:
        notes = connection.get_extended_notes(":ID:=%s AND (%s)" % (reference.id, " OR ".join(query_string_components)))
        notes = dict((note.citation_key, note) for note in notes)
        reference._saved_extended_notes_cks |= set(notes)
        if necessary("shelves"):
            prefix = "django-refdb-shelf-"
            prefix_length = len(prefix)
            reference.shelves = [citation_key[prefix_length:] for citation_key in notes if citation_key.startswith(prefix)]
        if necessary("global_pdf_available"):
            reference.global_pdf_available = "django-refdb-global-pdfs" in notes
        if necessary("users_with_offprint"):
            reference.users_with_offprint = notes.get("django-refdb-users-with-offprint-" + reference.citation_key, False)
        if necessary("relevance"):
            prefix = "django-refdb-relevance-"
            citation_keys = [citation_key for citation_key in notes if citation_key.startswith(prefix)]
            assert 0 <= len(citation_keys) <= 1
            reference.relevance = int(citation_keys[0][len(prefix):]) if citation_keys else False
        if necessary("comments"):
            reference.comments = notes.get("django-refdb-comments-" + reference.citation_key, False)
        if necessary("pdf_is_private"):
            reference.pdf_is_private[user_id] = "django-refdb-personal-pdfs-%d" % user_id in notes
        if necessary("creator"):
            prefix = "django-refdb-creator-"
            citation_keys = [citation_key for citation_key in notes if citation_key.startswith(prefix)]
            assert 0 <= len(citation_keys) <= 1
            reference.creator = int(citation_keys[0][len(prefix):]) if citation_keys else False
        if necessary("institute_publication"):
            reference.institute_publication = "django-refdb-institute-publication" in notes


def freeze(reference):
    u"""Creates extended notes from all set extended attributes.  This function
    fills the ``extended_notes`` attribute by looking at the values of the
    extended attributes (remember that they were generated from extended
    notes).  It must be called just before saving the object to RefDB.  (It is
    superfluous to call the function when writing the object to the cache.)

    Note that this function does not save the extended notes themselves.  It
    just prepares the object so that the *links* to extended notes are updated.
    In most cases, this is enough.  However, for global comments and “users
    with offprints”, there is a one-to-one relationship with an extended note
    which must be created and saved separately.

    :Parameters:
      - `reference`: the reference whose extended attributes should be
        converted to extended notes

    :type reference: `pyrefdb.Reference`
    """
    reference.extended_notes = pyrefdb.XNoteList()
    reference.extended_notes.extend("django-refdb-shelf-" + name for name in reference.shelves)
    if reference.global_pdf_available:
        reference.extended_notes.append("django-refdb-global-pdfs")
    if reference.users_with_offprint:
        reference.extended_notes.append(reference.users_with_offprint)
    if reference.relevance:
        reference.extended_notes.append("django-refdb-relevance-%d" % reference.relevance)
    if reference.comments:
        reference.extended_notes.append(reference.comments)
    reference.extended_notes.extend("django-refdb-personal-pdfs-%s" % user_id
                               for user_id, pdf_is_private in reference.pdf_is_private.iteritems() if pdf_is_private)
    if reference.creator:
        reference.extended_notes.append("django-refdb-creator-%d" % reference.creator)
    if reference.institute_publication:
        reference.extended_notes.append("django-refdb-institute-publication")


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
    u"THES": {u"publication_authors": _(u"Author"), u"publisher": _(u"Institution"), u"endpage": _(u"End page"),
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


def get_user_hash(user_id):
    u"""Retrieves the hash value for a user.  This is used for generating URLs
    to private PDFs.  The hash value is a shortened, salted SHA-1 hash of the
    user ID.  Note that it is guaranteed to be different from the user's RefDB
    password, see `refdb.get_password`.

    :Parameters:
      - `user_id`: the user ID whose hash should be retrieved

    :type user_id: int

    :Return:
      the hash value of the user

    :rtype: str
    """
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update("userhash")
    user_hash.update(str(user_id))
    return user_hash.hexdigest()[:10]


def pdf_file_url(reference, user, database):
    u"""Calculates the absolute URL of the uploaded PDF.  if a ``user`` is
    provided, it returns the link to the private PDF, if not, to the global
    one.  It returns ``None`` for each case which is not existing

    :Parameters:
      - `reference`: the reference whose PDF file path should be calculated
      - `user`: the user who tries to retrieve the file
      - `database`: the name of the RefDB database

    :type reference: ``pyrefdb.Reference``, with the ``extended_data``
      attribute
    :type user: ``django.contrib.auth.models.User``
    :type database: unicode

    :Return:
      the absolute URL to the global PDF, the absolute URL to the private PDF;

    :rtype: unicode, unicode
    """
    global_url = private_url = None
    if reference.pdf_is_private[user.id]:
        private_url = django.core.urlresolvers.reverse("refdb.views.reference.pdf",
                                                       kwargs={"database": database, "citation_key": reference.citation_key,
                                                               "username": user.username})
    if reference.global_pdf_available:
        global_url = django.core.urlresolvers.reverse("refdb.views.reference.pdf",
                                                      kwargs={"database": database, "citation_key": reference.citation_key})
    return global_url, private_url


def successful_response(request, success_report=None, view=None, kwargs={}, query_string=u"", forced=False):
    u"""After a POST request was successfully processed, there is typically a
    redirect to another page – maybe the main menu, or the page from where the
    add/edit request was started.

    The latter is appended to the URL as a query string with the ``next`` key,
    e.g.::

        /chantal/6-chamber_deposition/08B410/edit/?next=/chantal/samples/08B410a

    This routine generated the proper ``HttpResponse`` object that contains the
    redirection.  It always has HTTP status code 303 (“see other”).

    :Parameters:
      - `request`: the current HTTP request
      - `success_report`: an optional short success message reported to the
        user on the next view
      - `view`: the view name/function to redirect to; defaults to the main
        menu page (same when ``None`` is given)
      - `kwargs`: group parameters in the URL pattern that have to be filled
      - `query_string`: the *quoted* query string to be appended, without the
        leading ``"?"``
      - `forced`: If ``True``, go to ``view`` even if a “next” URL is
        available.  Defaults to ``False``.  See `bulk_rename.bulk_rename` for
        using this option to generate some sort of nested forwarding.

    :type request: ``HttpRequest``
    :type success_report: unicode
    :type view: str or function
    :type kwargs: dict
    :type query_string: unicode
    :type forced: bool

    :Return:
      the HTTP response object to be returned to the view's caller

    :rtype: ``HttpResponse``
    """
    return chantal_common.utils.successful_response(
        request, success_report, view or "refdb.views.main.main_menu", kwargs, query_string, forced)


class CommonBulkViewData(object):
    u"""Container class for data used in the functions related to conditional
    view processing (i.e. LastModified and ETags) as well as in the view
    itself.  The rationale for this class is that the conditional view
    functions have to calculate some data in a somewhat expensive manner – for
    example, it has to make a RefDB server connection.  This data is also used
    in the view itself, and it would be wasteful to calculate it there again.

    Thus, an instance of this class holds the data and is written as an
    attribute to the ``request`` object.
    """

    def __init__(self, refdb_connection, ids, **kwargs):
        u"""Class constructor.

        :Parameters:
          - `refdb_connection`: connection object to the RefDB server
          - `ids`: IDs of the found references (within ``offset`` and
            ``limit``)

        :type refdb_connection: ``pyrefdb.Connection``
        :type ids: list of str
        """
        self.refdb_connection, self.ids = refdb_connection, ids
        for key, value in kwargs.iteritems():
            setattr(self, key, value)


def _is_citation_key(citation_key_or_id):
    u"""Checks whether a string is a valid RefDB citation key.  This is a mere
    helper function for `citation_keys_to_ids` and `ids_to_citation_keys`.

    :Parameters:
      - `citation_key_or_id`: the RefDB citation key or RefDB ID which should
        be tested

    :type citation_key_or_id: str

    :Return:
      Whether the parameter was a citation key.  If the parameter was neither a
      citation key nor an ID, the behaviour is undefined.

    :rtype: bool
    """
    try:
        int(citation_key_or_id)
    except ValueError:
        return True
    return False


def citation_keys_to_ids(connection, citation_keys):
    u"""Returns a dictionary which maps the given citation keys to IDs.  The
    citation keys must exist in the RefDB database.  It is allowed to have IDs
    amongst the given citation keys.  Those are mapped to themselves.

    :Parameters:
      - `connection`: connection to the RefDB database
      - `citation_keys`: the citation keys to be converted

    :type connection: ``pyrefdb.Connection``
    :type citation_keys: list of str

    :Return:
      dictionary mapping the given citation keys to IDs

    :rtype: dict mapping str to str
    """
    result = {}
    missing_citation_keys = []
    for citation_key in citation_keys:
        if _is_citation_key(citation_key):
            try:
                result[citation_key] = models.Reference.objects.get(citation_key=citation_key).reference_id
            except models.Reference.DoesNotExist:
                missing_citation_keys.append(citation_key)
        else:
            result[citation_key] = citation_key
    if missing_citation_keys:
        references = connection.get_references(u" OR ".join(":CK:=" + citation_key
                                                            for citation_key in missing_citation_keys))
        for reference in references:
            models.Reference.objects.create(reference_id=reference.id, citation_key=reference.citation_key,
                                            database=connection.database)
            result[citation_key] = reference.id
    return result


def ids_to_citation_keys(connection, ids):
    u"""Returns a dictionary which maps the given IDs to citation keys.  The
    IDs must exist in the RefDB database.  It is allowed to have citation keys
    amongst the given ids.  Those are mapped to themselves.

    :Parameters:
      - `connection`: connection to the RefDB database
      - `ids`: the RefDB IDs to be converted

    :type connection: ``pyrefdb.Connection``
    :type ids: list of str

    :Return:
      dictionary mapping the given IDs to citation keys

    :rtype: dict mapping str to str
    """
    result = {}
    missing_ids = []
    for id_ in ids:
        if not _is_citation_key(id_):
            try:
                result[id_] = models.Reference.objects.get(reference_id=id_).citation_key
            except models.Reference.DoesNotExist:
                missing_ids.append(id_)
        else:
            result[id_] = id_
    if missing_ids:
        references = connection.get_references(u" OR ".join(":ID:=" + id_ for id_ in missing_ids))
        for reference in references:
            models.Reference.objects.create(reference_id=reference.id, citation_key=reference.citation_key,
                                            database=connection.database)
            result[id_] = reference.citation_key
    return result


def fetch_references(refdb_connection, ids, user):
    u"""Fetches all references needed for the references list in the view
    (bulk/main menu) from the RefDB database.  If possible, it takes the
    references from the cache.  The references contain also some extended
    attributes, see `fetch`.

    Additionally, a ``pdf_url`` attribute is added to all references containing
    the link to the (possibly private) PDF, or ``None``.

    :Parameters:
      - `refdb_connection`: connection object to the RefDB server
      - `ids`: IDs of the references
      - `user`: the current user

    :type refdb_connection: ``pyrefdb.Connection``
    :type ids: list of str
    :type user: ``django.contrib.auth.models.User``

    :Return:
      the references

    :rtype:
      list of ``pyrefdb.Reference``
    """
    all_references = cache.get_many(settings.REFDB_CACHE_PREFIX + id_ for id_ in ids)
    length_cache_prefix = len(settings.REFDB_CACHE_PREFIX)
    all_references = dict((cache_id[length_cache_prefix:], reference) for cache_id, reference in all_references.iteritems())
    missing_ids = set(ids) - set(all_references)
    if missing_ids:
        missing_references = refdb_connection.get_references(u" OR ".join(":ID:=" + id_ for id_ in missing_ids))
        missing_references = dict((reference.id, reference) for reference in missing_references)
        all_references.update(missing_references)
    references = [all_references[id_] for id_ in ids]
    for reference in references:
        fetch(reference, ["global_pdf_available", "pdf_is_private"], refdb_connection, user.id)
        cache.set(settings.REFDB_CACHE_PREFIX + reference.id, reference)
        global_url, private_url = pdf_file_url(reference, user, refdb_connection.database)
        reference.pdf_url = private_url or global_url
    return references


def prettyprint_title_abbreviation(abbreviated_title):
    u"""Inserts spaces after some full stops in the abbreviated title.  RefDB
    doesn't use spaces in abbreviated titles, like “Phys.Rev.”.  This function
    transforms this to “Phys. Rev.”.  The inserted spaces are breaking spaces.

    :Parameters:
      - `abbreviated_title`: The abbreviated title of the reference or
        abbreviated name of a journal

    :type abbreviated: unicode

    :Return:
      the abbreviated title with spaces after all full stops

    :rtype: unicode
    """
    result = u""
    position = 0
    while position < len(abbreviated_title):
        end = abbreviated_title.find(u".", position)
        if end == -1:
            end = len(abbreviated_title)
        else:
            end += 1
        result += abbreviated_title[position:end]
        if end != len(abbreviated_title) and unicodedata.category(abbreviated_title[end])[0] == "L":
            result += u" "
        position = end
    return result


def spawn_daemon(path_to_executable, *args):
    """Spawns a completely detached subprocess (i.e., a daemon).  Taken from
    http://stackoverflow.com/questions/972362/spawning-process-from-python
    which in turn was inspired by
    <http://code.activestate.com/recipes/278731/>.

    :Parameters:
      - `path_to_executable`: absolute path to the executable to be run
        detatched
      - `args`: all arguments to be passed to the subprocess

    :type path_to_executable: str
    :type args: list of str
    """
    try:
        pid = os.fork()
    except OSError, e:
        raise RuntimeError("1st fork failed: %s [%d]" % (e.strerror, e.errno))
    if pid != 0:
        os.waitpid(pid, 0)
        return
    os.setsid()
    try:
        pid = os.fork()
    except OSError, e:
        raise RuntimeError("2nd fork failed: %s [%d]" % (e.strerror, e.errno))
    if pid != 0:
        os._exit(0)
    try:
        maxfd = os.sysconf("SC_OPEN_MAX")
    except (AttributeError, ValueError):
        maxfd = 1024
    for fd in range(maxfd):
        try:
           os.close(fd)
        except OSError:
           pass
    os.open(os.devnull, os.O_RDWR)
    os.dup2(0, 1)
    os.dup2(0, 2)
    try:
        os.execv(path_to_executable, [path_to_executable] + list(filter(lambda arg: arg is not None, args)))
    except:
        os._exit(255)
