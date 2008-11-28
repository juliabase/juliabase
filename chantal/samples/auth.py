#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Handle authentication against an Active Directory.  For every user who
wants to log in (even the administrator), Chantal connects to the Active
Directory to see whether the login/password combination can bind to it.  If it
can but the user is not in Chantal's database, it is created and filled with
the data from the AD.  Of course, groups and permissions have yet to be set.

Every night the maintenance routine chacks which active users cannot be found
anymore in the AD, sets them to inactive and removes all their groups and
permissions.  See the `chantal.samples.views.maintenance.mark_inactive_users`
function.

A seldom but possible problem is if someone tries to login, he is known in the
AD, but it also known in Chantal as “inactive”.  This can mean one of two
things:

1. The user is a former collegue.  The admin must set him back to “active” and
   restore the groups and permissions.

2. It is a new user which has the same login as a former collegue
   coincidentally.  Then the old login name must be changed.  (Or the new one
   but this can only be done by the AD administrator.)

Portions of this module are taken from
<http://www.djangosnippets.org/snippets/501/>.
"""

from django.contrib.auth.models import User
from django.conf import settings
from django.core.mail import mail_admins
import ldap

class ActiveDirectoryBackend:
    def authenticate(self, username=None, password=None):
        try:
            is_valid = self.is_valid(username, password)
        except ldap.LDAPError, e:
            mail_admins("Chantal LDAP error", message=e.message["desc"])
            return None
        if not is_valid:
            return None
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            l = ldap.initialize(settings.AD_LDAP_URL)
            l.simple_bind_s(username, password)
            result = l.search_ext_s(
                settings.AD_SEARCH_DN, ldap.SCOPE_SUBTREE, "sAMAccountName=%s" % username, settings.AD_SEARCH_FIELDS)[0][1]
            l.unbind_s()
            user = User(username=username)
            if result.has_key("givenName"):
                user.first_name = result["givenName"][0]
            if result.has_key("sn"):
                user.last_name = result["sn"][0]
            if result.has_key("mail"):
                user.email = result["mail"][0]
            user.set_password(password)
            user.save()
        if not user.is_active:
            mail_admins("Inactive user back?", message=(u"""User “%s” tried to login but is set to inactive.

However, the Active Directory knows him/her.  There are two
possibilities: Either this is the former collegue, then just set
him/her to “active” and restore his/her permissions.  Or, they just
happen to have the same login, then change the former collegue's
login name.
""" % user.username).encode("utf-8"))
            return None
        return user
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
    def is_valid(self, username, password):
        if not password:
            return False
        binddn = "%s@%s" % (username, settings.AD_NT4_DOMAIN)
        try:
            l = ldap.initialize(settings.AD_LDAP_URL)
            l.simple_bind_s(binddn, password)
            l.unbind_s()
            return True
        except ldap.INVALID_CREDENTIALS:
            return False
