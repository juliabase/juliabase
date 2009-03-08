#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import django.contrib.auth.models
from django.dispatch import dispatcher
from django.db.models import signals
import pyrefdb
from django.conf import settings
from . import utils


def user_created(sender, **kwargs):
    user = kwargs["instance"]
    password = utils.get_refdb_password(user)
    pyrefdb.Connection(settings.CREDENTIALS["postgresql_user"], settings.CREDENTIALS["postgresql_password"]).\
        add_user("drefdbuser%d" % kwargs["instance"].id, password)

signals.post_save.connect(user_created, django.contrib.auth.models.User)
