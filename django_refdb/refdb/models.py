#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import django.contrib.auth.models
from django.contrib import admin
from django.db import models
from django.utils.translation import ugettext_lazy as _


class Reference(models.Model):
    reference_id = models.CharField(_(u"ID"), primary_key=True, max_length=10)
    last_modified = models.DateTimeField(_(u"last modified"), auto_now=True)

    class Meta:
        get_latest_by = "last_modified"

    def mark_modified(self):
        self.last_modified = datetime.datetime.now()
        self.user_modifications.all().delete()


class UserModification(models.Model):
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
