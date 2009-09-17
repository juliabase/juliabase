#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Models in the relational database for Django-RefDB.  Since almost
everything is stored in RefDB, Django-RefDB doesn't need many models of its
own.  
"""

import datetime
import django.contrib.auth.models
from django.contrib import admin
from django.db import models
from django.utils.translation import ugettext_lazy as _, ugettext


class Reference(models.Model):
    u"""Model for storing additional information for a reference.  Instances of
    this model are created every time a reference is accessed which hasn't such
    an instance yet.

    It is tempting to store additional field here that cannot be stored (yet)
    in RefDB.  But then, searching a combination of these field and intrinsic
    RefDB field is not feasible anymore.  So, all extension fields must be
    realised with extended notes within RefDB.

    Thus, I store here only things that are never used in a search.  So far,
    this is only the dates of last modification, both for the global data and
    for personal data (aka <libinfo> in RISX).
    """
    reference_id = models.CharField(_(u"ID"), primary_key=True, max_length=10)
    last_modified = models.DateTimeField(_(u"last modified"), auto_now=True)

    class Meta:
        get_latest_by = "last_modified"

    def mark_modified(self):
        u"""Marks the reference as a whole as modified.  This method must be
        called after a global RefDB field was changed.
        """
        self.last_modified = datetime.datetime.now()
        self.user_modifications.all().delete()


class UserModification(models.Model):
    u"""Model for storing a personal last-modification timestamp for a
    reference.  Each reference also contains a user-specific part, in RISX'
    <libinfo> field.  If a user changes their user-specific part, it would be
    wasteful to mark the reference modified for all users.  Thus, there are
    ``UserModification`` instances which store the personal timestamps.
    """
    user = models.ForeignKey(django.contrib.auth.models.User, related_name="user_modifications", verbose_name=_(u"user"))
    reference = models.ForeignKey(Reference, related_name="user_modifications", verbose_name=_(u"reference"))
    last_modified = models.DateTimeField(_(u"last modified"), auto_now=True)


languages = (
    ("de", u"Deutsch"),
    ("en", u"English"),
    )
u"""Contains all possible choices for `UserDetails.language`.
"""

class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"))
    language = models.CharField(_(u"language"), max_length=10, choices=languages, default="de")
    current_list = models.CharField(_(u"current references list"), max_length=255)

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")

    def __unicode__(self):
        return unicode(self.user)

admin.site.register(UserDetails)


class Shelf(models.Model):
    u"""Model for storing a “shelf” which contains an arbitrary numer of
    references.  It is intended to group references thematically.

    FixMe: Actually, this model is suportfluous.  It made sense when still
    Django's ``Group`` model was used for this but now, it is redundant since
    the shelves are stored as extended notes in RefDB.  However, it can stay as
    long as I don't have create/delete views for shelves, so that they can be
    at least generated through the admin interface.
    """
    name = models.CharField(_(u"name"), max_length=255, unique=True)

    class Meta:
        verbose_name = _(u"shelf")
        verbose_name_plural = _(u"shelves")

    def __unicode__(self):
        return ugettext(self.name)

admin.site.register(Shelf)
