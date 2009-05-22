#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pyrefdb
import django.contrib.auth.models
from django.db.models import signals
from . import utils


class SharedXNote(pyrefdb.XNote):

    def __init__(self, citation_key):
        super(SharedXNote, self).__init__(citation_key=citation_key)
        self.share = "public"


def add_refdb_user(sender, **kwargs):
    user = kwargs["instance"]
    utils.get_refdb_connection("root").add_user(utils.refdb_username(user.id), utils.get_refdb_password(user))
    utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-offprints-%d" % user.id))
    utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-personal-pdfs-%d" % user.id))
    utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-creator-%d" % user.id))

# It must be "post_save", otherwise, the ID may be ``None``.
signals.post_save.connect(add_refdb_user, sender=django.contrib.auth.models.User)


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
    utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-group-%d" % group.id))

# It must be "post_save", otherwise, the ID may be ``None``.
signals.post_save.connect(add_refdb_group, sender=django.contrib.auth.models.Group)


def remove_refdb_group(sender, **kwargs):
    group = kwargs["instance"]
    delete_extended_note(":NCK:=django-refdb-group-%d" % group.id)

signals.pre_delete.connect(remove_refdb_group, sender=django.contrib.auth.models.Group)
