#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions for the views.  In particular, this module
contains an additional abstraction layer between Django-RefDB and PyRefDB.
"""

from __future__ import absolute_import

import hashlib, re, urlparse
import pyrefdb
from django.conf import settings
from django.http import HttpResponse
from django.utils.encoding import iri_to_uri
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext as _
import django.contrib.auth.models
from . import models


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


class RefDBRollback(object):
    u"""Abstract base class for all rollback classes.  This is for having
    pseudo-transactions for RefDB operations.  So if a request fails due to a
    programming error, all changes in the RefDB database made during the
    request can be made undone.  This is not as reliable as low-level DB
    transactions but it's good enough.  In particular, it makes development of
    Django-RefDB more convenient.

    The actual rollback is done in the transaction middleware
    `refdb.middleware.transaction`.

    Note that the naming of the rollback classes is according to what they *do*
    rather than what they revert.
    """

    def __init__(self, user):
        u"""
        :Parameters:
          - `user`: currently logged-in user

        :type user: ``django.contrib.auth.models.User``
        """
        self.user = user

    def execute(self):
        u"""Executes the rollback.
        """
        raise NotImplementedError


class PickrefRollback(RefDBRollback):
    u"""Rollback class for re-picking references for a personal reference list.
    """

    def __init__(self, user, reference_id, list_name):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `reference_id`: RefDB ID of the reference to be re-picked
          - `list_name`: name of the personal reference list; if ``None``, add
            it to the user's default list

        :type user: ``django.contrib.auth.models.User``
        :type reference_id: int
        :type list_name: str or ``NoneType``
        """
        super(PickrefRollback, self).__init__(user)
        self.reference_id, self.list_name = reference_id, list_name

    def execute(self):
        get_refdb_connection(self.user).pick_references([self.reference_id], self.list_name)


class DumprefRollback(RefDBRollback):
    u"""Rollback class for un-picking references from a personal reference
    list.
    """

    def __init__(self, user, reference_id, list_name):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `reference_id`: RefDB ID of the reference to be un-picked
          - `list_name`: name of the personal reference list; if ``None``,
            remove it from the user's default list

        :type user: ``django.contrib.auth.models.User``
        :type reference_id: int
        :type list_name: str or ``NoneType``
        """
        super(DumprefRollback, self).__init__(user)
        self.reference_id, self.list_name = reference_id, list_name or None

    def execute(self):
        get_refdb_connection(self.user).dump_references([self.reference_id], self.list_name)


class UpdaterefRollback(RefDBRollback):
    u"""Rollback class for updating a reference (to its previous state).  Note
    that if the reference was retrieved with ``with_extended_notes=True``, this
    rollback also reconstructs the old links to extended notes (not the
    contents of the notes).

    Note that the given reference object should not be modified further because
    the class constructor doesn't make a deep copy of the object.  Thus, if you
    modify the object, the wrong object will be written back to the RefDB
    database after a failed request.
    """

    def __init__(self, user, reference):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `reference`: the original reference to be re-installed

        :type user: ``django.contrib.auth.models.User``
        :type reference: ``pyrefdb.Reference``
        """
        super(UpdaterefRollback, self).__init__(user)
        self.reference = reference

    def execute(self):
        get_refdb_connection(self.user).update_references(self.reference)


class DeleterefRollback(RefDBRollback):
    u"""Rollback class for deleting a reference which was added during the
    current request.
    """

    def __init__(self, user, citation_key):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `citation_key`: citation key of the added reference

        :type user: ``django.contrib.auth.models.User``
        :type citation_key: str
        """
        super(UpdaterefRollback, self).__init__(user)
        self.citation_key = citation_key

    def execute(self):
        reference_id = get_refdb_connection(self.user).get_references(":CK:=" + self.citation_key, "ids")[0]
        get_refdb_connection(self.user).delete_references([reference_id])


class AddnoteRollback(RefDBRollback):
    u"""Rollback class for re-adding a deleted extended note.  Note that the
    given extended note object must not be altered anymore, otherwise, the
    altered object will be re-added.
    """

    def __init__(self, user, extended_note):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `extended_note`: the extended note to be re-added

        :type user: ``django.contrib.auth.models.User``
        :type extended_note: ``pyrefdb.XNote``
        """
        super(AddnoteRollback, self).__init__(user)
        self.extended_note = extended_note

    def execute(self):
        get_refdb_connection(self.user).add_extended_notes(self.extended_note)


class DeletenoteRollback(RefDBRollback):
    u"""Rollback class for deleting a note which was added during the current
    request.
    """

    def __init__(self, user, note_citation_key):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `note_citation_key`: citation key of the added extended note

        :type user: ``django.contrib.auth.models.User``
        :type note_citation_key: str
        """
        super(DeletenoteRollback, self).__init__(user)
        self.note_citation_key = note_citation_key

    def execute(self):
        extended_note = get_refdb_connection(self.user).get_extended_notes(":NCK:=" + self.note_citation_key)[0]
        get_refdb_connection(self.user).delete_extended_notes([extended_note.id])


class UpdatenoteRollback(RefDBRollback):
    u"""Rollback class for updating an extended note (to its previous state).
    Note that the given extended note object must not be altered anymore,
    otherwise, the altered object will be restored.
    """

    def __init__(self, user, extended_note):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `extended_note`: the extended note to be restored

        :type user: ``django.contrib.auth.models.User``
        :type extended_note: ``pyrefdb.XNote``
        """
        super(UpdatenoteRollback, self).__init__(user)
        self.extended_note = extended_note

    def execute(self):
        get_refdb_connection(self.user).update_extended_notes(self.extended_note)


class LinknoteRollback(RefDBRollback):
    u"""Rollback class for re-establishing a link to an extended note which was
    removed during the current request.
    """

    def __init__(self, user, note_citation_key, reference_citation_key):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `note_citation_key`: citation key of the note to be linked to the
            reference
          - `reference_citation_key`: citation key of the reference

        :type user: ``django.contrib.auth.models.User``
        :type note_citation_key: str
        :type reference_citation_key: str
        """
        super(LinknoteRollback, self).__init__(user)
        self.note_citation_key, self.reference_citation_key = note_citation_key, reference_citation_key

    def execute(self):
        get_refdb_connection(self.user).add_note_links(":NCK:=" + self.note_citation_key,
                                                       ":CK:=" + self.reference_citation_key)


class UnlinknoteRollback(RefDBRollback):
    u"""Rollback class for unlinking to an extended note which was linked to a
    reference during the current request.
    """

    def __init__(self, user, note_citation_key, reference_citation_key):
        u"""
        :Parameters:
          - `user`: currently logged-in user
          - `note_citation_key`: citation key of the note to be unlinked from
            the reference
          - `reference_citation_key`: citation key of the reference

        :type user: ``django.contrib.auth.models.User``
        :type note_citation_key: str
        :type reference_citation_key: str
        """
        super(UnlinknoteRollback, self).__init__(user)
        self.note_citation_key, self.reference_citation_key = note_citation_key, reference_citation_key

    def execute(self):
        get_refdb_connection(self.user).remove_note_links(":NCK:=" + self.note_citation_key,
                                                          ":CK:=" + self.reference_citation_key)


def get_refdb_password(user):
    u"""Retrieves the RefDB password for a user.  For connection to RefDB, both
    username and password are computed from the Django user ID.  In this
    routine, I calculate the password, which is a shortened, salted SHA-1 hash
    of the user ID.

    :Parameters:
      - `user`: the user whose RefDB password should be retrieved

    :type user: ``django.contrib.auth.models.User``

    :Return:
      the RefDB password

    :rtype: str
    """
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update(str(user.id))
    return user_hash.hexdigest()[:10]


def refdb_username(user_id):
    u"""Retrieves the RefDB username for a user.  For connection to RefDB, both
    username and password are computed from the Django user ID.  In this
    routine, I calculate the username, which is the user ID with a constant
    prefix, namely `settings.REFDB_USERNAME_PREFIX`.

    :Parameters:
      - `user_id`: the Django user ID of the user

    :type user_id: int

    :Return:
      the RefDB username of the current user

    :rtype: str
    """
    # FixMe: For the sake of consistence, a full user object should be passed,
    # although only the ID is used.
    return settings.REFDB_USERNAME_PREFIX + str(user_id)


def get_refdb_connection(user):
    u"""Returns a RefDB connection object for the user, or returns a RefDB root
    connection.

    :Parameters:
      - `user`: the user whose RefDB password should be retrieved; if
        ``"root"`` is given instead, a connection with RefDB admin account is
        returned

    :type user: ``django.contrib.auth.models.User`` or str

    :Return:
      the RefDB connection object

    :rtype: ``pyrefdb.Connection``
    """
    if user == "root":
        return pyrefdb.Connection(settings.REFDB_USER, settings.REFDB_PASSWORD)
    else:
#         print refdb_username(user.id), get_refdb_password(user)
        return pyrefdb.Connection(refdb_username(user.id), get_refdb_password(user))


def get_lists(user, citation_key=None):
    u"""Retrieves the personal reference lists for a user.  Additionally, if
    ``citation_key`` is given, return a list of all personal reference lists in
    which this reference occurs.

    :Parameters:
      - `user`: the user whose personal reference lists should be retrieved
      - `citation_key`: citation key of a reference whose membership in the
        personal reference lists should be returned

    :type user: ``django.contrib.auth.models.User`` or str

    :Return:
      The personal reference lists of the user as a list of tupes (short name,
      verbose name), and a list of all reference lists (by their short names)
      in which the given reference occurs.  The latter is an empty list of no
      citation key was given.  The first list is ready-to-use as a ``choices``
      parameter in a choice form field.

    :rtype: list of (str, unicode), list of str
    """
    username = refdb_username(user.id)
    extended_notes = get_refdb_connection(user).get_extended_notes(":NCK:~^%s-" % username)
    choices = []
    initial = []
    for note in extended_notes:
        short_name = note.citation_key.partition("-")[2]
        if short_name:
            verbose_name = (note.content.text if note.content is not None else None) or short_name
            if verbose_name == username:
                verbose_name = _(u"main list")
            choices.append((short_name, verbose_name))
            if citation_key:
                for link in note.links:
                    if link[0] == "reference" and link[1] == citation_key:
                        initial.append(short_name)
                        break
    return choices, initial


def get_verbose_listname(short_listname, user):
    username = refdb_username(user.id)
    if short_listname == username:
        return _(u"main list")
    try:
        note = get_refdb_connection(user).get_extended_notes(":NCK:=%s-%s" % (username, short_listname))[0]
    except IndexError:
        return None
    return (note.content.text if note.content is not None else None) or short_listname


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
    if not isinstance(references, (list, tuple)):
        references = [references]
    timestamps = []
    for reference in references:
        try:
            id_ = reference.id
        except AttributeError:
            id_ = reference
        django_reference, __ = models.Reference.objects.get_or_create(reference_id=id_)
        try:
            user_modification = django_reference.user_modifications.get(user=user)
            timestamps.append(user_modification.last_modified)
        except models.UserModification.DoesNotExist:
            timestamps.append(django_reference.last_modified)
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
            self.shelves = set(int(citation_key[prefix_length:]) for citation_key in notes if citation_key.startswith(prefix))
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
    perpares the object so that the *links* to extended notes are updated.  In
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
