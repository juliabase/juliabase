#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Handle authentication against an Active Directory.  For every user who wants
to log in (even the administrator), JuliaBase connects to the Active Directory
to see whether the login/password combination can bind to it.  If it can but
the user is not in JuliaBase's database, it is created and filled with the data
from the AD, including permissions.  Groups are not used, and topics must be
set somewhere else because they are not stored in the AD.

Every night the maintenance routine checks which active users cannot be found
anymore in the AD, sets them to inactive and removes all their groups, topics,
and permissions.  See the `synchronize_with_ad` function.

A seldom but possible problem is if someone tries to login, he is known in the
AD, but it also known in JuliaBase as “inactive”.  This can mean one of two
things:

1. The user is a former collegue.  The admin must set him back to “active” and
   restore the groups, topics, and permissions.

2. It is a new user which has the same login as a former collegue
   coincidentally.  Then the old login name must be changed.  (Or the new one
   but this can only be done by the AD administrator.)

Portions of this module are inspired by
<http://www.djangosnippets.org/snippets/501/>.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from django.contrib.auth.models import User, Permission
from django.contrib.sessions.models import Session
from django.conf import settings
from django.core.mail import mail_admins
import ldap
from jb_common.models import Department
from jb_common.signals import maintain
from django.dispatch import receiver


class ActiveDirectoryBackend:

    supports_object_permissions = False
    supports_anonymous_user = False
    supports_inactive_user = False

    def authenticate(self, username=None, password=None):
        if not password:
            return None
        if username.lower() != username:
            # The LDAP doesn't check the case of the user name (whyever).
            # Therefore, in order to avoid creation of duplicates, all LDAP
            # accounts must have all-lowercase usernames.
            return None
        ldap_connection = LDAPConnection()
        if not ldap_connection.is_valid(username, password):
            return None
        user, created = User.objects.get_or_create(username=username)
        if not user.is_active:
            mail_admins("Inactive user back?", message=("""User “{0}” tried to login but is set to inactive.

However, the Active Directory knows him/her.  There are two
possibilities: Either this is the former collegue, then just set
him/her to “active”.  Or, they just happen to have the same login,
then change the former collegue's login name.
""".format(user.username)).encode("utf-8"))
        ldap_connection.synchronize_with_ad(user)
        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class LDAPConnection(object):
    """Class with represents an LDAP connection.  It creates and stores the
    connection instance itself and configures it.

    Instances of this shouldn't live for a long time because fetched AD data
    is cached.  So if the permissions of a user change while the instance is
    alive, this is not detected.  Typically, they live only for the duration
    of the login or the nightly maintenance process.
    """

    def __init__(self):
        self.connection = ldap.initialize(settings.AD_LDAP_URLS[0])
        self.connection.set_option(ldap.OPT_REFERRALS, 0)
        self.cached_ad_data = {}
        self.permissions_of_ad_groups = dict(
            (ad_groupname, set(Permission.objects.filter(codename__in=permission_codenames)))
            for ad_groupname, permission_codenames in settings.PERMISSIONS_OF_AD_GROUPS.items())
        self.managed_permissions = set(Permission.objects.filter(codename__in=settings.AD_MANAGED_PERMISSIONS))

    def is_valid(self, username, password):
        """Returns whether the username/password combination is known in the AD, and
        whether the user is a current member of one of the eligible departments.

        :Parameters:
          - `username`: the login name of the user
          - `password`: the cleartext password that the user has given

        :type username: unicode
        :type password: unicode

        :Return:
          whether the username/password combination is known in the AD, and
          the user is a member of one of the eligible departments.

        :rtype: bool
        """
        for ad_ldap_url in settings.AD_LDAP_URLS:
            try:
                binddn = "{0}@{1}".format(username, settings.AD_NT4_DOMAIN)
                bound_connection = ldap.initialize(ad_ldap_url)
                bound_connection.simple_bind_s(binddn.encode("utf-8"), password.encode("utf-8"))
                bound_connection.unbind_s()
            except ldap.INVALID_CREDENTIALS:
                return False
            except ldap.LDAPError as e:
                if settings.AD_LDAP_URLS.index(ad_ldap_url) + 1 == len(settings.AD_LDAP_URLS):
                    mail_admins("JuliaBase LDAP error", message=e.message["desc"])
                    return False
                continue
            if not self.is_eligible_ldap_member(username):
                return False
            self.connection = ldap.initialize(ad_ldap_url)
            self.connection.set_option(ldap.OPT_REFERRALS, 0)
            return True

    def get_ad_data(self, username):
        """Returns the dataset of the given user from the Active Directory.

        :Parameters:
          - `username`: the login name of the user

        :type username: unicode

        :Return:
          the dataset of the user as found in the AD; ``None`` if the user was
          not found

        :rtype: dict mapping str to list of str
        """
        try:
            ad_data = self.cached_ad_data[username]
        except KeyError:
            found = False
            for ad_ldap_url in settings.AD_LDAP_URLS:
                self.connection = ldap.initialize(ad_ldap_url)
                self.connection.set_option(ldap.OPT_REFERRALS, 0)
                try:
                    found, attributes = self.connection.search_ext_s(
                        settings.AD_SEARCH_DN, ldap.SCOPE_SUBTREE,
                        "(&(sAMAccountName={0}){1})".format(username, settings.AD_LDAP_ACCOUNT_FILTER or ""),
                        settings.AD_SEARCH_FIELDS)[0][:2]
                except ldap.LDAPError as e:
                    if settings.AD_LDAP_URLS.index(ad_ldap_url) + 1 == len(settings.AD_LDAP_URLS):
                        mail_admins("JuliaBase LDAP error", message=e.message["desc"])
                    else:
                        continue
                ad_data = attributes if found else None
                self.cached_ad_data[username] = ad_data
                break
        return ad_data

    def is_eligible_ldap_member(self, username):
        """Returns whether a user really is a member of one of the JuliaBase
        departments, or another authorised member of the LDAP directory.  This
        method even works if the user cannot be found in the AD at all (it
        returns ``False`` then, of course).

        :Parameters:
          - `username`: the login name of the user

        :type username: unicode

        :Return:
          whether the user is in one of the JuliaBase departments, or a
          specially authorised LDAP member

        :rtype: bool
        """
        attributes = self.get_ad_data(username)
        return attributes is not None and (
            not settings.AD_LDAP_DEPARTMENTS or
            attributes.get("department", [""])[0].decode("utf-8") in settings.AD_LDAP_DEPARTMENTS
            or username in settings.ADDITIONAL_LDAP_USERS)

    @staticmethod
    def get_group_names(attributes):
        """Returns all groups in the Active Directory with occur in the given
        attributes.  The attributes belong to a specific user and must have
        been fetched elsewhere.  Only the so-called “common names” of the
        groups (i.e. with the ``"CN"`` prefix in the LDAP path) are returned.

        :Parameters:
          - `attributes`: attributes of a specific user in the Active
            Directory

        :type attributes: dict mapping str to list

        :Return:
          the common names of all groups the user is a member of

        :rtype: set of str
        """
        group_paths = [path.decode("utf-8") for path in attributes.get("memberOf", [])]
        group_common_names = set()
        for path in group_paths:
            for part in path.split(","):
                if part.startswith("CN="):
                    group_common_names.add(part[3:])
                    break
        return group_common_names

    def synchronize_with_ad(self, user):
        """Update Django's dataset about a user according to the data found
        in the Active Directory.  This includes user permissions, which are
        set according to the AD groups the user is a member of.

        If the user is not found in the AD anymore, they are set to inactive,
        all groups, topic memberships, and permissions cleared, and their
        sessions purged.  (This way, we don't need the `ActiveUserMiddleware`.)

        Note that we don't map any AD data to Django *groups*.  Instead,
        everything is mapped to *permissions*.  The reason is that it doesn't
        make much sense to use convenience facilities like groups if
        everything is done automatically anyway.  It is still possible to use
        Django groups, however, any rights granted to users through Django
        groups can not be revoked by the Active Directory because we simply
        don't touch groups here.

        :Parameters:
          - `user`: the user whose data should be updated

        :type user: ``django.contrib.auth.models.User``
        """
        user.set_unusable_password()
        if self.is_eligible_ldap_member(user.username):
            attributes = self.get_ad_data(user.username)
            if "givenName" in attributes:
                user.first_name = attributes["givenName"][0].decode("utf-8")
            if "sn" in attributes:
                user.last_name = attributes["sn"][0].decode("utf-8")
            if "department" in attributes:
                jb_department_name = settings.AD_LDAP_DEPARTMENTS[attributes["department"][0].decode("utf-8")]
                user.jb_user_details.department, created = Department.objects.get_or_create(name=jb_department_name)
            user.email = attributes["mail"][0]
            user.jb_user_details.save()
            user.save()

            old_permissions = set(user.user_permissions.all())
            permissions = old_permissions - self.managed_permissions
            for group in self.get_group_names(attributes):
                permissions |= self.permissions_of_ad_groups.get(group, set())
            if permissions != old_permissions:
                user.user_permissions = permissions
        else:
            user.is_active = user.is_staff = user.is_superuser = False
            user.save()
            user.groups.clear()
            user.topics.clear()
            user.user_permissions.clear()
            for session in Session.objects.filter(expire_date__gte=datetime.datetime.now()).iterator():
                if session.get_decoded().get("_auth_user_id") == user.id:
                    session.delete()


@receiver(maintain)
def synchronize_users_with_ad(sender, **kwargs):
    """Signal listener which synchronises all active users without a usable
    password against the LDAP directory.  In particular, if a user cannot be
    found anymore or has switched the institute is set to “inactive”.
    Moreover, name, email, and permissions are updated.
    """
    ldap_connection = LDAPConnection()
    for user in User.objects.filter(is_active=True):
        if not user.has_usable_password():
            ldap_connection.synchronize_with_ad(user)
