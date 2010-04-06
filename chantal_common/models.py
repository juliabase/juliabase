#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""Models in the relational database for Chantal-Common.
"""

import django.contrib.auth.models
from django.db import models
from django.utils.translation import ugettext_lazy as _


languages = (
    ("en", u"English"),
    ("de", u"Deutsch"),
    )
u"""Contains all possible choices for `UserDetails.language`.
"""

class UserDetails(models.Model):
    u"""Model for further details about a user, beyond
    ``django.contrib.auth.models.User``.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, primary_key=True, verbose_name=_(u"user"),
                                related_name="chantal_user_details")
    language = models.CharField(_(u"language"), max_length=10, choices=languages, default="de")
    settings_last_modified = models.DateTimeField(_(u"settings last modified"), auto_now=True)
    external = models.BooleanField(_(u"is an external user"), default=False)

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")

    def __unicode__(self):
        return unicode(self.user)


class Project(models.Model):
    u"""Model for projects of the institution (institute/company).  Every
    sample belongs to at most one project.  Every user can be in an arbitrary
    number of projects.  The most important purpose of projects is to define
    permissions.  Roughly speaking, a user can view samples of their projects.

    The attribute ``restricted`` means that senior users (i.e. users with the
    permission ``"view_all_samples"``) cannot view samples of restricted
    projects (in order to make non-disclosure agreements with external partners
    possible).
    """
    name = models.CharField(_("name"), max_length=80, unique=True)
    members = models.ManyToManyField(django.contrib.auth.models.User, blank=True, verbose_name=_(u"members"),
                                     related_name="projects")
    restricted = models.BooleanField(_(u"restricted"), default=False)

    class Meta:
        verbose_name = _(u"project")
        verbose_name_plural = _(u"projects")

    def __unicode__(self):
        return unicode(self.name)
