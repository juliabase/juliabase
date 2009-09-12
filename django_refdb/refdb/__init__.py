#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Module for hooks into the ``User`` model of Django's authentication app as
well as the ``Shelf`` model.  They assure that every time a user or a shelf is
added or removed, this is reflected in the RefDB database.
"""

from __future__ import absolute_import

import pyrefdb
import django.contrib.auth.models
from django.db.models import signals
from . import utils
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
      - `sender`: the sender of the signal; will always be the ``User`` model
      - `instance`: the newly-added user
      - `created`: whether the user was newly created.

    :type sender: model class
    :type instance: ``django.contrib.auth.models.User``
    :type created: bool
    """
    if created:
        user = instance
        utils.get_refdb_connection("root").add_user(utils.refdb_username(user.id), utils.get_refdb_password(user))
        utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-personal-pdfs-%d" % user.id))
        utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-creator-%d" % user.id))

# It must be "post_save", otherwise, the ID may be ``None``.
signals.post_save.connect(add_refdb_user, sender=django.contrib.auth.models.User)


def add_user_details(sender, instance, created=True, **kwargs):
    u"""Adds a `models.UserDetails` instance for every newly-created Django
    user.  Hoever, you can also call it for existing users (``management.py``
    does it) because this function is idempotent.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``User`` model
      - `instance`: the newly-added user
      - `created`: whether the user was newly created.

    :type sender: model class
    :type instance: ``django.contrib.auth.models.User``
    :type created: bool
    """
    if created:
        refdb_app.UserDetails.objects.get_or_create(user=instance, current_list=utils.refdb_username(instance.id))

# It must be "post_save", otherwise, the ID may be ``None``.
signals.post_save.connect(add_refdb_user, sender=django.contrib.auth.models.User)


def delete_extended_note(citation_key):
    u"""Deletes an extended note from the RefDB database.  The note *must*
    exist.

    :Parameters:
      - `citation_key`: citation key of the extended note to be deleted

    :type citation_key: str
    """
    id_ = utils.get_refdb_connection("root").get_extended_notes(":NCK:=" + citation_key)[0].id
    utils.get_refdb_connection("root").delete_extended_notes([id_])


def remove_refdb_user(sender, instance, **kwargs):
    u"""Removes a newly-deleted Django user from RefDB.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``User`` model
      - `instance`: the newly-deleted user

    :type sender: model class
    :type instance: ``django.contrib.auth.models.User``
    """
    user = instance
    delete_extended_note("django-refdb-offprints-%d" % user.id)
    delete_extended_note("django-refdb-personal-pdfs-%d" % user.id)
    delete_extended_note("django-refdb-creator-%d" % user.id)
    utils.get_refdb_connection("root").remove_user(utils.refdb_username(user.id))

signals.pre_delete.connect(remove_refdb_user, sender=django.contrib.auth.models.User)


def add_shelf(sender, instance, created=True, **kwargs):
    u"""Adds a newly-added Django shelf to RefDB by adding an appropriate
    extended note.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``Shelf`` model
      - `instance`: the newly-added shelf
      - `created`: whether the shelf was newly created.

    :type sender: model class
    :type instance: ``refdb_app.Shelf``
    :type created: bool
    """
    if created:
        shelf = instance
        utils.get_refdb_connection("root").add_extended_notes(SharedXNote("django-refdb-shelf-%d" % shelf.id))

# It must be "post_save", otherwise, the ID may be ``None``.
signals.post_save.connect(add_shelf, sender=refdb_app.Shelf)


def remove_shelf(sender, instance, **kwargs):
    u"""Removes a newly-deleted Django shelf from RefDB by deleting its
    extended note.

    :Parameters:
      - `sender`: the sender of the signal; will always be the ``Shelf`` model
      - `instance`: the newly-deleted shelf

    :type sender: model class
    :type instance: ``refdb_app.Shelf``
    """
    shelf = instance
    delete_extended_note(":NCK:=django-refdb-shelf-%d" % shelf.id)

signals.pre_delete.connect(remove_shelf, sender=refdb_app.Shelf)
