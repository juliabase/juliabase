#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from . import utils
from . import models as refdb_app
from . import add_refdb_user, add_user_details, add_refdb_group, SharedXNote


def add_extended_note_if_nonexistent(citation_key):
    u"""Adds an extended note with the given citation key if it doesn't exist
    yet.  The note will be public (“shared”), but otherwise empty, i.e. no
    title, content etc.

    :Paramaters:
      - `citation_key`: the citation key of the extended note

    :type citation_key: str
    """
    if not utils.get_refdb_connection("root").get_extended_notes(":NCK:=" + citation_key):
        utils.get_refdb_connection("root").add_extended_notes(SharedXNote(citation_key))


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
    if interactive:
        confirm = raw_input("\nDo you want to reset all Django-RefDB-related extended notes "
                            "in the RefDB database? (yes/no): ")
        while confirm not in ["yes", "no"]:
            confirm = raw_input('Please enter either "yes" or "no": ')
        if confirm:
            ids = [note.id for note in utils.get_refdb_connection("root").get_extended_notes(":NCK:~^django-refdb-")]
            utils.get_refdb_connection("root").delete_extended_notes(ids)
            for user in django.contrib.auth.models.User.objects.all():
                add_refdb_user(sender=None, instance=user)
            for group in django.contrib.auth.models.Group.objects.all():
                add_refdb_group(sender=None, instance=group)
        for user in django.contrib.auth.models.User.objects.all():
            add_user_details(sender=None, instance=user)
    for relevance in range(1, 5):
        add_extended_note_if_nonexistent("django-refdb-relevance-%d" % relevance)
    add_extended_note_if_nonexistent("django-refdb-global-pdfs")
    add_extended_note_if_nonexistent("django-refdb-institute-publication")

signals.post_syncdb.connect(sync_extended_notes, sender=refdb_app)
