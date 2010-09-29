#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


u"""Models in the relational database for Chantal-Common.
"""

import hashlib
import django.contrib.auth.models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
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
    department = models.CharField(_(u"department"), max_length=30, blank=True)
    language = models.CharField(_(u"language"), max_length=10, choices=languages, default="de")
    browser_system = models.CharField(_(u"operating system"), max_length=10, default="windows")
    is_administrative = models.BooleanField(_(u"is administrative"), default=False)
    """``True`` if the account doesn't belong to an actual user, and thus
    shouldn't be eligible for things like "currently_responsible_person"."""

    class Meta:
        verbose_name = _(u"user details")
        verbose_name_plural = _(u"user details")

    def __init__(self, *args, **kwargs):
        super(UserDetails, self).__init__(*args, **kwargs)
        self._old = self.get_data_hash()

    def __unicode__(self):
        return unicode(self.user)

    def get_data_hash(self):
        u"""Get the hash of all fields that change the HTML's appearance,
        e.g. language, skin, browser type etc.

        :Return:
          the data hash value

        :rtype: str
        """
        hash_ = hashlib.sha1()
        hash_.update(self.language)
        hash_.update("\x03")
        hash_.update(self.browser_system)
        return hash_.hexdigest()


class Topic(models.Model):
    u"""Model for topics of the institution (institute/company).  Every sample
    belongs to at most one topic.  Every user can be in an arbitrary number of
    topics.  The most important purpose of topics is to define permissions.
    Roughly speaking, a user can view samples of their topics.

    The attribute ``confidential`` means that senior users (i.e. users with the
    permission ``"view_all_samples"``) cannot view samples of confidential
    topics (in order to make non-disclosure agreements with external partners
    possible).
    """
    name = models.CharField(_("name"), max_length=80, unique=True)
    members = models.ManyToManyField(django.contrib.auth.models.User, blank=True, verbose_name=_(u"members"),
                                     related_name="topics")
    confidential = models.BooleanField(_(u"confidential"), default=False)

    class Meta:
        verbose_name = _(u"topic")
        verbose_name_plural = _(u"topics")
        _ = lambda x: x
        permissions = (("can_edit_all_topics", _("Can edit all topics, and can add new topics")),
                       ("can_edit_their_topics", _("Can edit topics that he/she is a member of")))

    def __unicode__(self):
        return unicode(self.name)

    def get_name_for_user(self, user):
        u"""Determine the topic's name that can be shown to a certain user.  If
        the topic is confidential and the user is not a memeber of the project,
        he must not read the actual topic name.  Therefore, a generic name is
        generated.  This is used e.g. for the “My Samples” list on the main
        menu page.

        :Parameters:
          - `user`: the user for which the name should be displayed

        :type user: ``django.contrib.auth.models.User``
        """
        if self.confidential and not self.members.filter(pk=user.pk).exists():
            return _(u"topic #{number} (confidential)").format(number=self.id)
        else:
            return self.name


class PolymorphicModel(models.Model):
    u"""Abstract model class, which provides the attribute ``actual_instance``.
    This solves the problem that Django's ORM does not implement automatic
    resolution of polymorphy.  For example, if you get a list of Toppings,
    they're just Toppings.  However sometimes, you must have the actual object,
    i.e. CheeseTopping, SalamiTopping etc.  Then, ``topping.actual_instance``
    will give just that.

    Simply derive the top-level model class from this one, and then you can
    easily resolve polymorphy in it and its derived classes.
    """
    content_type = models.ForeignKey(ContentType, null=True, blank=True)
    actual_object_id = models.PositiveIntegerField(null=True, blank=True)
    actual_instance = generic.GenericForeignKey("content_type", "actual_object_id")

    def save(self, *args, **kwargs):
        u"""Saves the instance and assures that `actual_instance` is set.
        """
        super(PolymorphicModel, self).save(*args, **kwargs)
        if not self.actual_object_id:
            self.actual_instance = self
            super(PolymorphicModel, self).save()

    class Meta:
        abstract = True


class ErrorPage(models.Model):
    u"""Model for storing HTML pages which contain error messages.  This is
    intended for connections with non-browser agents which request for JSON
    responses.  If the request fails, the resulting JSON contains a link to
    view the full error page.  Such pages are expired after some time.
    """
    hash_value = models.CharField(_("hash value"), max_length=40, primary_key=True)
    user = models.ForeignKey(django.contrib.auth.models.User, blank=True, verbose_name=_(u"user"),
                             related_name="error pages")
    requested_url = models.TextField(_("requested URL"), blank=True)
    html = models.TextField("HTML")
    timestamp = models.DateTimeField(_(u"timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _(u"error page")
        verbose_name_plural = _(u"error pages")
