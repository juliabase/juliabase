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

    The citation key is stored only because it is used in an xnote dataset, so
    that I can calculate the timestamp of last modification of user references
    lists faster.  FixMe: Once
    http://sourceforge.net/tracker/?func=detail&aid=2872243&group_id=26091&atid=385994
    is solved, one could probably get rid of the ``citation_key`` field.
    """
    database = models.CharField(_(u"database"), max_length=255)
    reference_id = models.CharField(_(u"ID"), max_length=10)
    citation_key = models.CharField(_(u"citation key"), max_length=255)
    last_modified = models.DateTimeField(_(u"last modified"), auto_now=True)

    class Meta:
        get_latest_by = "last_modified"
        unique_together = (("database", "reference_id"), ("database", "citation_key"))

    def mark_modified(self, user=None):
        u"""Marks the reference as modified.  This method must be called after
        a global RefDB field was changed.  If `user` is given, the reference is
        only marked modified for this user, e.g. if only his private notes for
        the reference were changed.  This is not limited to core RefDB fields.
        It may also be the “extended attributes” or the membership in shelves
        or references lists, or uploaded PDFs.

        Note that you needn't call the ``save`` method afterwards.

        :Parameters:
          - `user`: the user who touched the reference; ``None`` if the changes
            also affect other users

        :type user: ``django.contrib.auth.models.User``
        """
        if user:
            user_modification, created = UserModification.objects.get_or_create(user=user, reference=self)
            if not created:
                user_modification.save()
        else:
            self.user_modifications.all().delete()
            self.save()

    def get_last_modification(self, user):
        u"""Determines the timestamp of the last modification of this
        reference.  The modification is “seend” from the user, i.e. personal
        changes that he has made to the reference (e.g. editing private notes)
        are taken into account.  Personal changes of other users are ignored.

        :Parameters:
          - `user`: the user for which the last modification of this reference
            should be determined

        :type user: ``django.contrib.auth.models.User``

        :Return:
          the timestamp of the last modification

        :rtype: ``datetime.datetime``
        """
        try:
            user_modification = self.user_modifications.get(user=user)
            return user_modification.last_modified
        except UserModification.DoesNotExist:
            return self.last_modified

admin.site.register(Reference)


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
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"),
                                related_name="refdb_user_details")
    language = models.CharField(_(u"language"), max_length=10, choices=languages, default="de")
    settings_last_modified = models.DateTimeField(_(u"settings last modified"), auto_now=True)

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")

    def __unicode__(self):
        return unicode(self.user)

admin.site.register(UserDetails)


class DatabaseAccount(models.Model):
    database = models.CharField(_(u"database"), max_length=255)
    user = models.ForeignKey(django.contrib.auth.models.User, related_name="database_accounts", verbose_name=_(u"user"))
    current_list = models.CharField(_(u"current references list"), max_length=255)
    last_modified = models.DateTimeField(_(u"database settings last modified"), auto_now=True)

    class Meta:
        verbose_name = _(u"database account")
        verbose_name_plural = _(u"database accounts")
        unique_together = ("database", "user")

    def __unicode__(self):
        return u"%s/%s" % (self.database, self.user)

admin.site.register(DatabaseAccount)
