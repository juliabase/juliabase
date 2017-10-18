#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


import django.forms as forms
import django.contrib.auth.models
from jb_common.models import Topic, Department
from jb_common.utils.base import get_really_full_name, sorted_users_by_first_name


def _user_choices_by_department(user, include=(), exclude=()):
    """Returns a choices list ready-to-be-used in multiple- and single-selection
    widgets.  Basically, it consists of all users in the departments that the
    user wants to see accorint to the `show_users_from_departments` field.  It
    collapses the list automatically if only one department is present.  Note
    that no entry for “empty choice” is added.  This must be done by the
    caller, if necessary.

    :param user: the currently logged-in user
    :param include: list of users to be included additionally
    :param exclude: list of users to be excluded

    :type user: django.contrib.auth.models.User
    :type include: list of django.contrib.auth.models.User
    :type exclude: list of django.contrib.auth.models.User

    :return:
      list of choices, ready to be used in a `ChoiceField` or
      `MultipleChoiceField`

    :rtype: list of (int, str) or list of (str, list of (int, str))
    """
    choices = []
    for department in Department.objects.all():
        users_from_department = set(user for user in include if user.jb_user_details.department == department)
        if department in user.samples_user_details.show_users_from_departments.all():
            users_from_department |= set(django.contrib.auth.models.User.objects.
                                         filter(is_active=True, jb_user_details__department=department))
        users_from_department -= set(user for user in exclude if user.jb_user_details.department == department)
        if users_from_department:
            choices.append((department.name, [(user.pk, get_really_full_name(user))
                                              for user in sorted_users_by_first_name(users_from_department)]))
    departmentless_users = [user for user in include
                            if user in django.contrib.auth.models.User.objects.filter(jb_user_details__department=None)]
    if departmentless_users:
        choices.append(("", [(user.pk, get_really_full_name(user))
                             for user in sorted_users_by_first_name(departmentless_users)]))
    if len(choices) == 1:
        choices = choices[0][1]
    return choices


class UserField(forms.ChoiceField):
    """Form field class for the selection of a single user.  This can be the
    new currently responsible person for a sample, or the person you wish to
    send “My Samples” to.
    """

    def set_users(self, user, additional_user=None):
        """Set the user list shown in the widget.  You *must* call this method (or
        :py:meth:`~jb_common.utils.views.UserField.set_users_without`) in the
        constructor of the form in which you use this field, otherwise the
        selection box will remain emtpy.  The selection list will consist of
        all currently active users, plus the given additional user if any.

        :param user: Thr user who wants to see the user list
        :param additional_user: Optional additional user to be included into the
            list.  Typically, it is the current user for the process to be
            edited.

        :type user: django.contrib.auth.models.User
        :type additional_user: django.contrib.auth.models.User
        """
        self.choices = [("", 9 * "-")] + \
                       _user_choices_by_department(user, include=[additional_user] if additional_user else [])


    def set_users_without(self, user, excluded_user):
        """Set the user list shown in the widget.  You *must* call this method (or
        :py:meth:`~jb_common.utils.views.UserField.set_users`) in the
        constructor of the form in which you use this field, otherwise the
        selection box will remain emtpy.  The selection list will consist of
        all currently active users, minus the given user.

        :param user: Thr user who wants to see the user list
        :param excluded_user: User to be excluded from the list.  Typically, it
            is the currently logged-in user.

        :type excluded_user: django.contrib.auth.models.User
        """
        self.choices = [("", 9 * "-")] + \
                       _user_choices_by_department(user, exclude=[excluded_user] if excluded_user else [])

    def clean(self, value):
        value = super(UserField, self).clean(value)
        if value:
            return django.contrib.auth.models.User.objects.get(pk=int(value))


class MultipleUsersField(forms.MultipleChoiceField):
    """Form field class for the selection of zero or more users.  This can be
    the set of members for a particular topic.
    """

    def __init__(self, *args, **kwargs):
        super(MultipleUsersField, self).__init__(*args, **kwargs)
        self.widget.attrs["size"] = 15

    def set_users(self, user, additional_users=[]):
        """Set the user list shown in the widget.  You *must* call this method
        in the constructor of the form in which you use this field, otherwise
        the selection box will remain emtpy.  The selection list will consist
        of all currently active users, plus the given additional users if any.

        :param user: Thr user who wants to see the user list
        :param additional_users: Optional additional users to be included into
            the list.  Typically, it is the current users for the topic whose
            memberships are to be changed.

        :type additional_users: iterable of django.contrib.auth.models.User
        """
        self.choices = _user_choices_by_department(user, include=additional_users)
        if not self.choices:
            self.choices = (("", 9 * "-"),)

    def clean(self, value):
        if value == [""]:
            value = []
        value = super(MultipleUsersField, self).clean(value)
        return django.contrib.auth.models.User.objects.in_bulk([int(pk) for pk in set(value)]).values()


class TopicField(forms.ChoiceField):
    """Form field class for the selection of a single topic.  This can be
    the topic for a sample or a sample series, for example.
    """

    def set_topics(self, user, additional_topic=None):
        """Set the topic list shown in the widget.  You *must* call this
        method in the constructor of the form in which you use this field,
        otherwise the selection box will remain emtpy.  The selection list will
        consist of all currently active topics, plus the given additional
        topic if any.  The “currently active topics” are all topics with
        at least one active user amongst its members.

        :param user: the currently logged-in user
        :param additional_topic: Optional additional topic to be included
            into the list.  Typically, it is the current topic of the sample,
            for example.

        :type user: django.contrib.auth.models.User
        :type additional_topic: `jb_common.models.Topic`
        """
        def topics_and_sub_topics(parent_topics):
            for topic in parent_topics:
                name = 2 * " " + str(topic) if topic.has_parent() else str(topic)
                self.choices.append((topic.pk, name))
                child_topics = topic.child_topics.all()
                if child_topics:
                    topics_and_sub_topics(sorted(child_topics, key=lambda topic: topic.name.lower()))

        self.choices = [("", 9 * "-")]
        if not user.is_superuser:
            all_topics = Topic.objects.filter(members__is_active=True).filter(department=user.jb_user_details.department).distinct()
            user_topics = user.topics.all()
            top_level_topics = \
                set(topic for topic in all_topics if (not topic.confidential or topic in user_topics) and not topic.has_parent())
            if additional_topic:
                top_level_topics.add(additional_topic.get_top_level_topic())
        else:
            top_level_topics = set(topic for topic in Topic.objects.iterator() if not topic.has_parent())
        top_level_topics = sorted(top_level_topics, key=lambda topic: topic.name.lower())
        topics_and_sub_topics(top_level_topics)

    def clean(self, value):
        value = super(TopicField, self).clean(value)
        if value:
            return Topic.objects.get(pk=int(value))
