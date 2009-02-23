#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.contrib.auth import models
from django.dispatch import dispatcher
from django.db.models import signals

def user_created(sender, **kwargs):
    print kwargs

signals.post_save.connect(user_created, models.User)
