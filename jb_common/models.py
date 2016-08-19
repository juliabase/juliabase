#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Models in the relational database for JuliaBase-Common.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six
from django.utils.encoding import python_2_unicode_compatible

import hashlib
import django.contrib.auth.models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
import django.utils.timezone
from django.utils.translation import ugettext_lazy as _, ugettext
import jb_common.search


@python_2_unicode_compatible
class Department(models.Model):
    """Model to determine which process belongs to which department.
    Each department has its own processes, so users should only be
    able to see the processes of their department.
    """
    name = models.CharField(_("name"), max_length=30, unique=True)
    app_label = models.CharField(_("app label"), max_length=30)

    class Meta:
        ordering = ["name"]
        verbose_name = _("department")
        verbose_name_plural = _("departments")

    def __str__(self):
        return self.name


languages = (
    ("en", "English"),
    ("de", "Deutsch"),
    )
"""Contains all possible choices for `UserDetails.language`.
"""

@python_2_unicode_compatible
class UserDetails(models.Model):
    """Model for further details about a user, beyond
    django.contrib.auth.models.User.  Here, you have all data about a
    registered user that is not stored by Django's user model itself.
    """
    user = models.OneToOneField(django.contrib.auth.models.User, models.CASCADE, primary_key=True, verbose_name=_("user"),
                                related_name="jb_user_details")
    department = models.ForeignKey(Department, models.CASCADE, verbose_name=_("department"), related_name="user_details",
                                   null=True, blank=True)
    """The department of the user and all samples that he/she is the currently
    responsible for.  If it is ``None``, the user must not appear in the
    select-user choice fields (e.g. for moving a sample to another user).  So
    take care that if you compare this with another department which may also
    be ``None``, that in case both are ``None``, the result is ``False``.
    Every sensible JuliaBase installation will have at least one department."""
    language = models.CharField(_("language"), max_length=10, choices=languages, default="en")
    browser_system = models.CharField(_("operating system"), max_length=10, default="windows")
    layout_last_modified = models.DateTimeField(_("layout last modified"), auto_now_add=True)
    """Timestamp at which the settings which affect appearance of the HTML were
    changed for the last time."""

    class Meta:
        verbose_name = _("user details")
        verbose_name_plural = _("user details")

    def __init__(self, *args, **kwargs):
        super(UserDetails, self).__init__(*args, **kwargs)
        self._old = self.get_data_hash()

    def __str__(self):
        return six.text_type(self.user)

    def save(self, *args, **kwargs):
        if self._old != self.get_data_hash():
            self.layout_last_modified = django.utils.timezone.now()
        super(UserDetails, self).save(*args, **kwargs)

    def get_data_hash(self):
        """Get the hash of all fields that change the HTML's appearance,
        e.g. language, skin, browser type etc.  This hash is used to decide
        whether a cached sample instance of another user can be used for this
        one.

        :return:
          the data hash value

        :rtype: str
        """
        hash_ = hashlib.sha1()
        hash_.update(self.language.encode("utf-8"))
        hash_.update(b"\x03")
        hash_.update(self.browser_system.encode("utf-8"))
        return hash_.hexdigest()


@python_2_unicode_compatible
class Topic(models.Model):
    """Model for topics of the institution (institute/company).  Every sample
    belongs to at most one topic.  Every user can be in an arbitrary number of
    topics.  The most important purpose of topics is to define permissions.
    Roughly speaking, a user can view samples of their topics.

    The attribute ``confidential`` means that senior users (i.e. users with the
    permission ``"view_every_sample"``) cannot view samples of confidential
    topics (in order to make non-disclosure agreements with external partners
    possible).
    """
    name = models.CharField(_("name"), max_length=80)
    members = models.ManyToManyField(django.contrib.auth.models.User, blank=True, verbose_name=_("members"),
                                     related_name="topics")
    confidential = models.BooleanField(_("confidential"), default=False)
    department = models.ForeignKey(Department, models.CASCADE, verbose_name=_("department"), related_name="topic")
    parent_topic = models.ForeignKey("self", models.CASCADE, verbose_name=_("parent topic"), related_name="child_topics",
                                    blank=True, null=True)
    manager = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, verbose_name=_("topic manager"),
                                related_name="managed_topics")

    class Meta:
        ordering = ["name"]
        verbose_name = _("topic")
        verbose_name_plural = _("topics")
        unique_together = ("name", "department", "parent_topic")
        _ = lambda x: x
        default_permissions = ()
        permissions = (("add_topic", _("Can add new topics")),
                       ("change_topic", _("Can edit all topics")),
                       ("edit_their_topics", _("Can edit topics that he/she is a manager of")))

    def __str__(self):
        return six.text_type(self.name)

    @classmethod
    def get_search_tree_node(cls):
        """Class method for generating the search tree node for this model
        instance.

        :return:
          the tree node for this model instance

        :rtype: `jb_common.search.SearchTreeNode`
        """
        search_fields = [jb_common.search.TextSearchField(cls, "name")]
        related_models = {}
        return jb_common.search.SearchTreeNode(cls, related_models, search_fields)

    def get_name_for_user(self, user):
        """Determine the topic's name that can be shown to a certain user.  If
        the topic is confidential and the user is not a memeber of the project,
        he must not read the actual topic name.  Therefore, a generic name is
        generated.  This is used e.g. for the “My Samples” list on the main
        menu page.

        :param user: the user for which the name should be displayed

        :type user: django.contrib.auth.models.User
        """
        if self.confidential and not self.members.filter(pk=user.pk).exists():
            return _("topic #{number} (confidential)").format(number=self.id)
        else:
            return self.name

    def has_parent(self):
        """Looks if the topic has a superordinate topic.

        :return:
          ``True`` if the topic has a superordinate topic and ``False`` if not.

        :rtype: bool
        """
        return True if self.parent_topic else False

    def save(self):
        """When the topic was edited, the sub topics must be updated.
        """
        assert not Topic.objects.filter(name=self.name, department=self.department, parent_topic=self.parent_topic).exists()
        super(Topic, self).save()
        for child_topic in self.child_topics.iterator():
            child_topic.confidential = self.confidential
            child_topic.members = self.members.all()
            child_topic.manager = self.manager
            child_topic.save()

    def get_top_level_topic(self):
        """
        :return:
          the most upper topic from this topic.

        :rtype: `Topic`
        """
        if self.parent_topic:
            return self.parent_topic.get_top_level_topic()
        else:
            return self


class PolymorphicModel(models.Model):
    """Abstract model class, which provides the attribute
    :py:attr:`actual_instance`.  This solves the problem that Django's ORM does
    not implement automatic resolution of polymorphy.  For example, if you get
    a list of Toppings, they're just Toppings.  However sometimes, you must
    have the actual object, i.e. CheeseTopping, SalamiTopping etc.  Then,
    ``topping.actual_instance`` will give just that.

    FixMe: One could replace this with
    <https://django-model-utils.readthedocs.org/en/latest/managers.html#inheritancemanager>.

    Simply derive the top-level model class from this one, and then you can
    easily resolve polymorphy in it and its derived classes.
    """
    content_type = models.ForeignKey(ContentType, models.CASCADE, null=True, blank=True, editable=False)
    actual_object_id = models.PositiveIntegerField(null=True, blank=True, editable=False)
    actual_instance = GenericForeignKey("content_type", "actual_object_id")

    def save(self, *args, **kwargs):
        """Saves the instance and assures that `actual_instance` is set.
        """
        super(PolymorphicModel, self).save(*args, **kwargs)
        if not self.actual_object_id:
            self.actual_instance = self
            super(PolymorphicModel, self).save()

    class Meta:
        abstract = True


class ErrorPage(models.Model):
    """Model for storing HTML pages which contain error messages.  This is
    intended for connections with non-browser agents which request for JSON
    responses.  If the request fails, the resulting JSON contains a link to
    view the full error page.  Such pages are expired after some time.
    """
    hash_value = models.CharField(_("hash value"), max_length=40, primary_key=True)
    user = models.ForeignKey(django.contrib.auth.models.User, models.CASCADE, null=True, blank=True, verbose_name=_("user"),
                             related_name="error_pages")
    requested_url = models.TextField(_("requested URL"), blank=True)
    html = models.TextField("HTML")
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)

    class Meta:
        verbose_name = _("error page")
        verbose_name_plural = _("error pages")


_ = ugettext
