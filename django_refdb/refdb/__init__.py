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

signals.pre_save.connect(add_refdb_user, sender=django.contrib.auth.models.User)


def remove_refdb_user(sender, **kwargs):
    user = kwargs["instance"]
    utils.get_refdb_connection("root").remove_user(utils.refdb_username(user.id))

signals.pre_delete.connect(remove_refdb_user, sender=django.contrib.auth.models.User)


def add_refdb_group(sender, **kwargs):
    group = kwargs["instance"]
    note = pyrefdb.XNote()
    note.citation_key = "django-refdb-group-%d" % group.id
    utils.get_refdb_connection("root").add_extended_note(note)

signals.pre_save.connect(add_refdb_group, sender=django.contrib.auth.models.Group)


def remove_refdb_group(sender, **kwargs):
    group = kwargs["instance"]
    id_ = utils.get_refdb_connection("root").get_extended_notes(":NCK:=django-refdb-group-%d" % group.id)[0].id
    utils.get_refdb_connection("root").delete_extended_note([id_])

signals.pre_delete.connect(remove_refdb_group, sender=django.contrib.auth.models.Group)
