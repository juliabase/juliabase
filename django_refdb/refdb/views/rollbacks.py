#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Classes necessary for RefDB database rollbacks.  By registering rollbacks,
one can simulate something like transactions in other databases.  Thus, if the
HTTP request fails for some reason, the rollbacks are executed and the old
state in RefDB is restored.  Hopefully.
"""

from __future__ import absolute_import

from .. import refdb


__all__ = ["PickrefRollback", "DumprefRollback", "UpdaterefRollback", "DeleterefRollback",
           "AddnoteRollback", "DeletenoteRollback", "UpdatenoteRollback", "LinknoteRollback", "UnlinknoteRollback"]


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
        refdb.get_connection(self.user).pick_references([self.reference_id], self.list_name)


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
        refdb.get_connection(self.user).dump_references([self.reference_id], self.list_name)


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
        refdb.get_connection(self.user).update_references(self.reference)


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
        reference_id = refdb.get_connection(self.user).get_references(":CK:=" + self.citation_key, "ids")[0]
        refdb.get_connection(self.user).delete_references([reference_id])


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
        refdb.get_connection(self.user).add_extended_notes(self.extended_note)


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
        extended_note = refdb.get_connection(self.user).get_extended_notes(":NCK:=" + self.note_citation_key)[0]
        refdb.get_connection(self.user).delete_extended_notes([extended_note.id])


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
        refdb.get_connection(self.user).update_extended_notes(self.extended_note)


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
        refdb.get_connection(self.user).add_note_links(":NCK:=" + self.note_citation_key,
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
        refdb.get_connection(self.user).remove_note_links(":NCK:=" + self.note_citation_key,
                                                                ":CK:=" + self.reference_citation_key)
