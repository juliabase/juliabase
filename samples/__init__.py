#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import absolute_import

from django.db.models import signals
import django.contrib.auth.models
from . import models as samples_app
from chantal_common import models as chantal_common_app


def touch_sample_settings_m2m(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.touch_sample_settings()

signals.m2m_changed.connect(touch_sample_settings_m2m, sender=samples_app.UserDetails.my_samples.through)


def touch_sample_settings(sender, instance, **kwargs):
    try:
        instance.user.samples_user_details.touch_sample_settings()
    except samples_app.UserDetails.DoesNotExist:
        # We can safely ignore it.  The initial value of
        # sample_settings_timestamp is correctly set anyway.
        pass

signals.post_save.connect(touch_sample_settings, sender=chantal_common_app.UserDetails)


def add_user_details(sender, instance, **kwargs):
    samples_app.UserDetails.objects.get_or_create(user=instance)

signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)
