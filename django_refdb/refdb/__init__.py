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


u"""Module for hooks into the ``DatabaseAccount`` model.  They assure that
every time a database account for a particular user is added or removed, this
is reflected in the RefDB database.
"""

from __future__ import absolute_import

import pyrefdb
import django.contrib.auth.models
from django.db.models import signals
from . import refdb
from . import models as refdb_app


class SharedXNote(pyrefdb.XNote):
    u"""Wrapper class for ``pyrefdb.XNote`` with the ``share`` attribute set to
    ``"public"``.  It just makes instantiation such extended notes easier.
    """

    def __init__(self, citation_key):
        super(SharedXNote, self).__init__(citation_key=citation_key)
        self.share = "public"


def add_refdb_user(sender, instance, created=True, **kwargs):
    u"""Adds a newly-created Django user to RefDB.

    :Parameters:
      - `sender`: the sender of the signal; will always be the
        ``DatabaseAccount`` model
      - `instance`: the newly-added database account
      - `created`: whether the user was newly created.

    :type sender: model class
    :type instance: `refdb_app.DatabaseAccount`
    :type created: bool
    """
    if created:
        database_account = instance
        connection = refdb.get_connection("root", database_account.database)
        user = database_account.user
        connection.add_user(refdb.get_username(user.id), refdb.get_password(user))
        connection.add_extended_notes(SharedXNote("django-refdb-personal-pdfs-%d" % user.id))
        connection.add_extended_notes(SharedXNote("django-refdb-creator-%d" % user.id))

# It must be "post_save", otherwise, the ID may be ``None``.
signals.post_save.connect(add_refdb_user, sender=refdb_app.DatabaseAccount)


def delete_extended_note(citation_key, database):
    u"""Deletes an extended note from the RefDB database.  The note *must*
    exist.

    :Parameters:
      - `citation_key`: citation key of the extended note to be deleted
      - `database`: the name of the RefDB database

    :type citation_key: str
    :type database: unicode
    """
    connection = refdb.get_connection("root", database)
    id_ = connection.get_extended_notes(":NCK:=" + citation_key)[0].id
    connection.delete_extended_notes([id_])


def remove_refdb_user(sender, instance, **kwargs):
    u"""Removes a newly-deleted Django user from RefDB.

    :Parameters:
      - `sender`: the sender of the signal; will always be the
        ``DatabaseAccount`` model
      - `instance`: the newly-added database account

    :type sender: model class
    :type instance: `refdb_app.DatabaseAccount`
    """
    user_id = instance.user.id
    database = instance.database
    delete_extended_note("django-refdb-personal-pdfs-%d" % user_id, database)
    delete_extended_note("django-refdb-creator-%d" % user_id, database)
    refdb.get_connection("root", database).remove_user(refdb.get_username(user_id))

signals.pre_delete.connect(remove_refdb_user, sender=refdb_app.DatabaseAccount)
