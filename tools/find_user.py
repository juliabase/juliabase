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


from __future__ import unicode_literals
import os, sys, socket
hostname = socket.gethostname()
if hostname in ["mandy", "olga"]:
    os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
    sys.path.append("/home/chantal/chantal")

from django.conf import settings
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, load_backend
from django.contrib.auth.models import AnonymousUser


def user_from_session_key(session_key):
    """Taken from <http://djangosnippets.org/snippets/1276/>.
    """
    session_engine = __import__(settings.SESSION_ENGINE, {}, {}, [""])
    session_wrapper = session_engine.SessionStore(session_key)
    user_id = session_wrapper.get(SESSION_KEY)
    backend = session_wrapper.get(BACKEND_SESSION_KEY)
    if backend:
        auth_backend = load_backend(backend)
        if user_id and auth_backend:
            return auth_backend.get_user(user_id)
        else:
            return AnonymousUser()
    else:
        return None


session_key = raw_input("Session key: ")
user = user_from_session_key(session_key)
if user:
    print ", ".join((user.username, user.get_full_name(), user.email))
else:
    print "Session ID not found."
