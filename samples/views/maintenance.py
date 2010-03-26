#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Module with database maintenance work.  It is supposed to be called in
regular intervals, e.g. once every night.  You may trigger its processing with
the following shell command::

    wget --post-data= --output-document=- http://127.0.0.1/maintenance/{hash} \\
        > /dev/null

The hash can be found in ``urls.py``.

So far, it sets users which can't be found anymore in the Active Directory to
“inactive”, and expires all feed entries which are older than six weeks.
"""

from __future__ import absolute_import

import datetime
from django.http import HttpResponse, Http404
import django.contrib.auth.models
from samples import models
from django.conf import settings
from django.core.mail import mail_admins
import ldap


def expire_feed_entries():
    u"""Deletes all feed entries which are older than six weeks.
    """
    now = datetime.datetime.now()
    six_weeks_ago = now - datetime.timedelta(days=42)
    for entry in models.FeedEntry.objects.filter(timestamp__lt=six_weeks_ago):
        entry.delete()


def mark_inactive_users():
    u"""Sets all users which can't be found anymore in the central Active
    Directory to “inactive”.  It also removes all special rights from them, and
    all group memberships.
    """
    try:
        l = ldap.initialize(settings.AD_LDAP_URL)
        l.set_option(ldap.OPT_REFERRALS, 0)
        for user in django.contrib.auth.models.User.objects.filter(is_active=True):
            found = l.search_ext_s(settings.AD_SEARCH_DN, ldap.SCOPE_SUBTREE, "(sAMAccountName=%s)" % user.username,
                                   settings.AD_SEARCH_FIELDS)[0][0]
            if not found:
                user.is_active = user.is_staff = user.is_superuser = False
                user.save()
                user.groups.clear()
                user.user_permissions.clear()
    except ldap.LDAPError, e:
        mail_admins("Chantal LDAP error", message=e.message["desc"])


def maintenance(request):
    u"""Perform database maintenance.  Its URL should never be accessable or
    guessable by anyone.  Instead, it is an internal Chantal secret.

    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the HTTP response object

    :rtype: ``HttpResponse``
    """
    if request.method == "POST":
        expire_feed_entries()
        mark_inactive_users()
        return HttpResponse(content_type="text/plain; charset=utf-8", status=204)
    else:
        raise Http404
