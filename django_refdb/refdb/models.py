#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import django.contrib.auth.models
from django.db import models
from django.utils.translation import ugettext_lazy as _

class Reference(models.Model):
    reference_id = models.CharField(_(u"ID"), primary_key=True, max_length=10)
    last_modified = models.DateTimeField(_(u"last modified"), auto_now=True)

    class Meta:
        get_latest_by = "last_modified"

    def mark_modified(self):
        self.last_modified = datetime.datetime.now()
        self.user_modifications.delete()

class UserModification(models.Model):
    user = models.ForeignKey(django.contrib.auth.models.User, related_name="user_modifications", verbose_name=_(u"user"))
    reference = models.ForeignKey(Reference, related_name="user_modifications", verbose_name=_(u"reference"))
    last_modified = models.DateTimeField(_(u"last modified"), auto_now=True)
