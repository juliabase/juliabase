#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pyrefdb
import django.contrib.auth.models
from django.db.models import signals
from . import utils
from . import models as refdb_app
from . import add_refdb_user, add_refdb_group, SharedXNote


def add_extended_note_if_nonexistent(citation_key):
    if not utils.get_refdb_connection("root").get_extended_notes(":NCK:=" + citation_key):
        utils.get_refdb_connection("root").add_extended_notes(SharedXNote(citation_key))


def sync_extended_notes(sender, created_models, interactive, **kwargs):
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
    for relevance in range(1, 5):
        add_extended_note_if_nonexistent("django-refdb-relevance-%d" % relevance)
    add_extended_note_if_nonexistent("django-refdb-global-pdfs")

signals.post_syncdb.connect(sync_extended_notes, sender=refdb_app)
