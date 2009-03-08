#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import hashlib
from django.conf import settings
import pyrefdb


def get_refdb_password(user):
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update(str(user.id))
    return user_hash.hexdigest()[:10]

def get_refdb_connection(user):
    return pyrefdb.Connection("drefdbuser%d" % user.id, get_refdb_password(user))
