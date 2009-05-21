#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import django.contrib.auth.models
from django.db.models import signals
import pyrefdb
from django.conf import settings
from . import utils


def add_refdb_user(sender, **kwargs):
    user = kwargs["instance"]
    utils.get_refdb_connection("root").add_user(utils.refdb_username(user.id), utils.get_refdb_password(user))
    utils.get_refdb_connection("root").add_extended_notes(pyrefdb.XNote(citation_key="django-refdb-offprints-%d" % user.id))
    utils.get_refdb_connection("root").add_extended_notes(
        pyrefdb.XNote(citation_key="django-refdb-personal-pdfs-%d" % user.id))
    utils.get_refdb_connection("root").add_extended_notes(pyrefdb.XNote(citation_key="django-refdb-creator-%d" % user.id))

signals.pre_save.connect(add_refdb_user, sender=django.contrib.auth.models.User)


def delete_extended_note(citation_key):
    id_ = utils.get_refdb_connection("root").get_extended_notes(":NCK:=" + citation_key)[0].id
    utils.get_refdb_connection("root").delete_extended_notes([id_])


def remove_refdb_user(sender, **kwargs):
    user = kwargs["instance"]
    delete_extended_note("django-refdb-offprints-%d" % user.id)
    delete_extended_note("django-refdb-personal-pdfs-%d" % user.id)
    delete_extended_note("django-refdb-creator-%d" % user.id)
    utils.get_refdb_connection("root").remove_user(utils.refdb_username(user.id))

signals.pre_delete.connect(remove_refdb_user, sender=django.contrib.auth.models.User)


def add_refdb_group(sender, **kwargs):
    group = kwargs["instance"]
    utils.get_refdb_connection("root").add_extended_note(pyrefdb.XNote(citation_key="django-refdb-group-%d" % group.id))

signals.pre_save.connect(add_refdb_group, sender=django.contrib.auth.models.Group)


def remove_refdb_group(sender, **kwargs):
    group = kwargs["instance"]
    delete_extended_note(":NCK:=django-refdb-group-%d" % group.id)

signals.pre_delete.connect(remove_refdb_group, sender=django.contrib.auth.models.Group)


def add_extended_note_if_nonexistent(citation_key):
    if not utils.get_refdb_connection("root").get_extended_notes(":NCK:=" + citation_key):
        utils.get_refdb_connection("root").add_extended_notes(pyrefdb.XNote(citation_key=citation_key))


def sync_extended_notes(sender, interactive, **kwargs):
    if interactive:
        confirm = raw_input("\nDo you want to reset all Django-RefDB-related extended notes "
                            "in the RefDB database? (yes/no): ")
        while confirm not in ('yes', 'no'):
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

signals.post_syncdb.connect(sync_extended_notes)
