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


u"""This is the synchronisation of the RefDB database with the Django database.
It is activated by::

    ./manage.py syncdb

and answering "yes" to the respective question.  The code doesn't change the
references in the RefDB database themselves but it creates needed extended
notes (all with the ``"django-refdb-"`` prefix in their citation keys).
Additionally, it creates RefDB user accounts for all Django user accounts.
"""

from __future__ import absolute_import

import pyrefdb
import django.contrib.auth.models
from django.db.models import signals
from . import refdb
from . import models as refdb_app
from . import SharedXNote


def add_extended_note_if_nonexistent(citation_key, database):
    u"""Adds an extended note with the given citation key if it doesn't exist
    yet.  The note will be public (“shared”), but otherwise empty, i.e. no
    title, content etc.

    :Paramaters:
      - `citation_key`: the citation key of the extended note
      - `database`: the name of the RefDB database

    :type citation_key: str
    :type database: unicode
    """
    connection = refdb.get_connection("root", database)
    if not connection.get_extended_notes(":NCK:=" + citation_key):
        connection.add_extended_notes(SharedXNote(citation_key))


def ask_user(question, interactive):
    u"""Asks the user a question and returns whether the user has replied with
    “yes” to it.  If ``manage.py`` is not in interactive mode, this function
    always returns ``False``.

    :Parameters:
      - `question`: the question to be asked; it should end in a question mark
      - `interactive`: whether the user has requestion interactive mode; it is
        the same parameter as the `sync_extended_notes` parameter of the same
        name

    :type question: str
    :type interactive: bool

    :Return:
      whether the user has replied with “yes” to the question

    :rtype: bool
    """
    if interactive:
        confirm = raw_input("\n" + question + " (yes/no): ")
        while confirm not in ["yes", "no"]:
            confirm = raw_input('Please enter either "yes" or "no": ')
        return confirm == "yes"
    else:
        return False
    

def sync_extended_notes(sender, created_models, interactive, **kwargs):
    u"""Sychronises the RefDB database with the Django database.  See the
    description of this module for further information.

    :Parameters:
      - `sender`: the sender of the signal; will always be the module
        ``refdb.models``
      - `created_models`: the model classes from any app which syncdb has
        created so far
      - `interactive`: whether interactive questions are allowed on the command
        line

    :type sender: module
    :type created_models: list of ``django.db.models.Model``
    :type interactive: bool
    """
    databases = refdb.get_connection("root", None).list_databases()
    if ask_user("Do you want to reset user-specific extended notes "
                "of a previous Django-RefDB in some or all RefDB databases?", interactive):
        for database in databases:
            if ask_user("Do you want to reset user-specific extended notes "
                        "of the RefDB database \"%s\"?" % database, interactive):
                connection = refdb.get_connection("root", database)
                ids = [note.id for note in connection.get_extended_notes(
                        ":NCK:~^django-refdb-users-with-offprint OR :NCK:~^django-refdb-personal-pdfs OR "
                        ":NCK:~^django-refdb-creator")]
                connection.delete_extended_notes(ids)
    for database in databases:
        for relevance in range(1, 5):
            add_extended_note_if_nonexistent("django-refdb-relevance-%d" % relevance, database)
        add_extended_note_if_nonexistent("django-refdb-global-pdfs", database)
        add_extended_note_if_nonexistent("django-refdb-institute-publication", database)

signals.post_syncdb.connect(sync_extended_notes, sender=refdb_app)
