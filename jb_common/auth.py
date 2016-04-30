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


"""Handle authentication against an Active Directory.  For every user who wants
to log in (even the administrator), JuliaBase connects to the Active Directory
to see whether the login/password combination can bind to it.  If it can but
the user is not in JuliaBase's database, it is created and filled with the data
from the AD, including permissions.  Groups are not used, and topics must be
set somewhere else because they are not stored in the AD.

Every night the maintenance routine checks which active users cannot be found
anymore in the AD, sets them to inactive and removes all their groups, topics,
and permissions.  See the :py:meth:`~LDAPConnection.synchronize_with_ad`
function.

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
import django.utils.six as six

from django.contrib.auth.models import User, Permission
from django.contrib.sessions.models import Session
import django.utils.timezone
from django.conf import settings
from django.core.mail import mail_admins
import ldap3
from jb_common.models import Department
from jb_common.signals import maintain
from django.dispatch import receiver


# FixMe: Apparently, ldap3 moved to long constant names and back again.  Thus,
# this should be removed eventually.
try:
    ldap3.SUBTREE
except AttributeError:
    ldap3.SUBTREE = ldap3.SEARCH_SCOPE_WHOLE_SUBTREE


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
        self.cached_ad_data = {}
        self.permissions_of_ad_groups = dict(
            (ad_groupname, set(Permission.objects.filter(codename__in=permission_codenames)))
            for ad_groupname, permission_codenames in settings.LDAP_GROUPS_TO_PERMISSIONS.items())
        managed_permissions_codenames = set().union(*settings.LDAP_GROUPS_TO_PERMISSIONS.values())
        self.managed_permissions = set(Permission.objects.filter(codename__in=managed_permissions_codenames))

    def is_valid(self, username, password):
        """Returns whether the username/password combination is known in the AD, and
        whether the user is a current member of one of the eligible departments.

        :param username: the login name of the user
        :param password: the cleartext password that the user has given

        :type username: unicode
        :type password: unicode

        :return:
          whether the username/password combination is known in the AD, and
          the user is a member of one of the eligible departments.

        :rtype: bool
        """
        for ad_ldap_url in settings.LDAP_URLS:
            try:
                server = ldap3.Server(ad_ldap_url, use_ssl=True)
                connection = ldap3.Connection(server, user=settings.LDAP_LOGIN_TEMPLATE.format(username=username).encode("utf-8"),
                                              password=password.encode("utf-8"), raise_exceptions=True, read_only=True)
                connection.bind()
                connection.unbind()
            except ldap3.LDAPInvalidCredentialsResult:
                return False
            except ldap3.LDAPException as e:
                latest_error = e
                continue
            if not self.is_eligible_ldap_member(username):
                return False
            return True
        else:
            try:
                # FixMe: This branch is only for Python 2
                message = latest_error.message["desc"]
            except AttributeError:
                message = str(latest_error)
            mail_admins("JuliaBase LDAP error", message)
            return False

    def get_ad_data(self, username):
        """Returns the dataset of the given user from the Active Directory.

        :param username: the login name of the user

        :type username: unicode

        :return:
          the dataset of the user as found in the AD; ``None`` if the user was
          not found

        :rtype: dict mapping str to list of str
        """
        try:
            ad_data = self.cached_ad_data[username]
        except KeyError:
            for ad_ldap_url in settings.LDAP_URLS:
                server = ldap3.Server(ad_ldap_url, use_ssl=True)
                connection = ldap3.Connection(server, raise_exceptions=True, read_only=True)
                try:
                    connection.bind()
                    connection.search(search_base=settings.LDAP_SEARCH_DN,
                                      search_scope=ldap3.SUBTREE,
                                      search_filter="(&(sAMAccountName={0}){1})".format(username, settings.LDAP_ACCOUNT_FILTER),
                                      attributes=list({b"mail", b"givenName", b"sn", b"department", b"memberOf"}.union(
                                                    settings.LDAP_ADDITIONAL_ATTRIBUTES)))
                except ldap3.LDAPException as e:
                    if settings.LDAP_URLS.index(ad_ldap_url) + 1 == len(settings.LDAP_URLS):
                        try:
                            # FixMe: This branch is only for Python 2
                            message = e.message["desc"]
                        except AttributeError:
                            message = str(e)
                        mail_admins("JuliaBase LDAP error", message)
                    else:
                        continue
                ad_data = connection.response[0]["attributes"] if connection.response[0]["type"] == "searchResEntry" else None
                self.cached_ad_data[username] = ad_data
                connection.unbind()
                break
        return ad_data

    def is_eligible_ldap_member(self, username):
        """Returns whether a user really is a member of one of the JuliaBase
        departments, or another authorised member of the LDAP directory.  This
        method even works if the user cannot be found in the AD at all (it
        returns ``False`` then, of course).

        :param username: the login name of the user

        :type username: unicode

        :return:
          whether the user is in one of the JuliaBase departments, or a
          specially authorised LDAP member

        :rtype: bool
        """
        attributes = self.get_ad_data(username)
        return attributes is not None and (
            not settings.LDAP_DEPARTMENTS or
            attributes.get("department", [""])[0] in settings.LDAP_DEPARTMENTS
            or username in settings.LDAP_ADDITIONAL_USERS)

    @staticmethod
    def get_group_names(attributes):
        """Returns all groups in the Active Directory with occur in the given
        attributes.  The attributes belong to a specific user and must have
        been fetched elsewhere.  Only the so-called “common names” of the
        groups (i.e. with the ``"CN"`` prefix in the LDAP path) are returned.

        :param attributes: attributes of a specific user in the Active
            Directory

        :type attributes: dict mapping str to list

        :return:
          the common names of all groups the user is a member of

        :rtype: set of str
        """
        group_paths = [path for path in attributes.get("memberOf", [])]
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
        sessions purged.  (This way, we don't need the
        :py:class:`jb_common.middleware.ActiveUserMiddleware`.)

        Note that we don't map any AD data to Django *groups*.  Instead,
        everything is mapped to *permissions*.  The reason is that it doesn't
        make much sense to use convenience facilities like groups if
        everything is done automatically anyway.  It is still possible to use
        Django groups, however, any rights granted to users through Django
        groups can not be revoked by the Active Directory because we simply
        don't touch groups here.

        :param user: the user whose data should be updated

        :type user: django.contrib.auth.models.User
        """
        user.set_unusable_password()
        if self.is_eligible_ldap_member(user.username):
            attributes = self.get_ad_data(user.username)
            if "givenName" in attributes:
                user.first_name = attributes["givenName"][0]
            if "sn" in attributes:
                user.last_name = attributes["sn"][0]
            if "department" in attributes:
                jb_department_name = settings.LDAP_DEPARTMENTS[attributes["department"][0]]
                try:
                    user.jb_user_details.department = Department.objects.get(
                        name=settings.LDAP_ADDITIONAL_USERS[user.username])
                except KeyError:
                    user.jb_user_details.department = Department.objects.get(name=jb_department_name)
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
            for session in Session.objects.filter(expire_date__gte=django.utils.timezone.now()).iterator():
                if session.get_decoded().get("_auth_user_id") == user.id:
                    session.delete()


@receiver(maintain)
def synchronize_users_with_ad(sender, **kwargs):
    """Signal listener which synchronises all active users without a usable
    password against the LDAP directory.  In particular, if a user cannot be
    found anymore or has switched the institute is set to “inactive”.
    Moreover, name, email, and permissions are updated.

    *Important*: This listener is only activated if this module is imported,
    which does not happen (as of Django 1.8) for JuliaBase's ``manage.py
    maintenance`` command.  Thus, you need to import this module where you
    import your own signals module, e.g. in the ``ready()`` method of your
    ``AppConfig`` class.
    """
    ldap_connection = LDAPConnection()
    for user in User.objects.filter(is_active=True):
        if not user.has_usable_password():
            ldap_connection.synchronize_with_ad(user)
