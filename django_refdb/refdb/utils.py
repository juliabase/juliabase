#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions for the views.  In particular, this module
contains an additional abstraction layer between Django-RefDB and PyRefDB.
"""

from __future__ import absolute_import

import hashlib, re, urlparse
import pyrefdb
from django.conf import settings
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext as _
import django.contrib.auth.models
from . import models


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
        return pyrefdb.Connection(settings.DATABASE_USER, settings.DATABASE_PASSWORD)
    else:
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
            verbose_name = note.content.text or short_name
            if verbose_name == username:
                verbose_name = _(u"main list")
            choices.append((short_name, verbose_name))
            if citation_key:
                for link in note.links:
                    if link[0] == "reference" and link[1] == citation_key:
                        initial.append(short_name)
                        break
    return choices, initial


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


class ExtendedData(object):
    u"""Class holding extended data for references.  RefDB can't store all data
    that Django-RefDB needs to be stored with every reference.  This data is
    put into an ``ExtendedData`` object and injected into the RefDB reference
    object into the ``extended_data`` attribute.  This way, the ``pyrefdb``
    routines still work, and all data is in the same instance.

    Actually this extended data is stored in extended notes in the RefDB
    databse.  However, this data is not conveniently accessible by the Django
    routines.  Therefore, the extended notes are “converted” to
    ``ExtendedData`` when extracting the reference, and converted back when
    storing the reference into the RefDB database.

    :ivar groups: Django group IDs this reference belongs to
    :ivar global_pdf_available: whether a PDF file downloadable by everyone is
      available
    :ivar users_with_offprint: IDs of users with physical copies of this
      reference
    :ivar relevance: value from 1 to 4, denoting the relevance of the reference
    :ivar comments: globally visible comments on the reference
    :ivar users_with_personal_pdfs: IDs of users who uploaded a private PDF
      file of the reference
    :ivar creator: ID of the user who added this reference
    :ivar institute_publication: whether this reference is an institute
      publication

    :ivar groups: list of int
    :ivar global_pdf_available: bool
    :ivar users_with_offprint: set of int
    :ivar relevance: int or ``NoneType``
    :ivar comments: ``pyrefdb.XNote`` or ``NoneType``
    :ivar users_with_personal_pdfs: set of int
    :ivar creator: int
    :ivar institute_publication: bool
    """

    def __init__(self):
        self.groups = []
        self.global_pdf_available = False
        self.users_with_offprint = set()
        self.relevance = None
        self.comments = None
        self.users_with_personal_pdfs = set()
        self.creator = None
        self.institute_publication = False


citation_key_pattern = re.compile(r"""django-refdb-(?:
                                   group-(?P<group_id>\d+) |
                                   (?P<global_pdf>global-pdfs) |
                                   offprints-(?P<user_id_with_offprint>\d+) |
                                   relevance-(?P<relevance>\d+) |
                                   comments-(?P<reference_ck>.+) |
                                   personal-pdfs-(?P<user_id_with_personal_pdf>\d+) |
                                   creator-(?P<creator_id>\d+) |
                                   (?P<institute_publication>institute-publication)
                                  )$""", re.VERBOSE)

def extended_notes_to_data(references):
    u"""Walks through the extended notes of references and convert extended
    data found there to `ExtendedData` objects added to the references.  For
    each given reference, the links extended notes are searched for “special”
    extended notes containing extended data (see `ExtendedData`).  From this,
    an `ExtendedData` object is contructed, which is written as an
    ``extended_data`` attribute into the respective reference.  This way, the
    Django views can access this data much more conveniently.

    Attention: The given references are modified in-place.
    
    :Parameters:
      - `references`: the references into which the ``extended_data``
        attributes should be injected

    :type references: iterable of ``pyrefdb.Reference``
    """
    for reference in references:
        reference.extended_data = ExtendedData()
        for extended_note in reference.extended_notes:
            match = citation_key_pattern.match(extended_note.citation_key)
            if match:
                group_id, global_pdf, user_id_with_offprint, relevance, \
                    reference_ck, user_id_with_personal_pdf, creator_id, institute_publication = match.groups()
                if group_id:
                    reference.extended_data.groups.append(int(group_id))
                elif global_pdf:
                    reference.extended_data.global_pdf_available = True
                elif user_id_with_offprint:
                    reference.extended_data.users_with_offprint.add(int(user_id_with_offprint))
                elif relevance:
                    reference.extended_data.relevance = int(relevance)
                elif reference_ck:
                    reference.extended_data.comments = extended_note
                elif user_id_with_personal_pdf:
                    reference.extended_data.users_with_personal_pdfs.add(int(user_id_with_personal_pdf))
                elif creator_id:
                    reference.extended_data.creator = int(creator_id)
                elif institute_publication:
                    reference.extended_data.institute_publication = True


def extended_data_to_notes(reference):
    u"""Takes the ``extended_data`` attribute of the given reference and convert
    it to extended notes and links to extended notes.  This way, the reference
    is ready for being written back to the RefDB database.  Obviously, this is
    done after all modifications to the reference have been taken place (in
    particular the modifications to the extended data).

    Attention: The given reference in modified in-place.

    :Parameters:
      - `reference`: the reference whose extended data should be converted

    :type reference: ``pyrefdb.Reference``
    """
    reference.extended_notes = pyrefdb.XNoteList()
    extended_data = reference.extended_data
    for group_id in extended_data.groups:
        reference.extended_notes.append("django-refdb-group-%d" % group_id)
    if extended_data.global_pdf_available:
        reference.extended_notes.append("django-refdb-global-pdfs")
    for user_id in extended_data.users_with_offprint:
        reference.extended_notes.append("django-refdb-offprints-%d" % user_id)
    if extended_data.relevance:
        reference.extended_notes.append("django-refdb-relevance-%d" % extended_data.relevance)
    if extended_data.comments:
        reference.extended_notes.append(extended_data.comments)
    for user_id in extended_data.users_with_personal_pdfs:
        reference.extended_notes.append("django-refdb-personal-pdfs-%d" % user_id)
    if extended_data.creator:
        reference.extended_notes.append("django-refdb-creator-%d" % extended_data.creator)
    if extended_data.institute_publication:
        reference.extended_notes.append("django-refdb-institute-publication")
