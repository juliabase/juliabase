#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import absolute_import

from django.db.models import signals
import django.contrib.auth.models
from . import models as samples_app
from chantal_common import models as chantal_common_app


def touch_sample_settings_m2m(sender, instance, action, **kwargs):
    u"""Touch the “sample settings modified” field in the ``UserDetails``.
    This function is called whenever the “My Samples” of the user change.  It
    assures that when a sample datasheet is displayed next time, it is not
    taken from the browser cache because the “is among My Samples” may be
    outdated otherwise.

    This is only a compromise.  It would be more efficient to expire the
    browser cache only for those samples that have actually changed in “My
    Samples”.  But the gain would be small and the code significantly more
    complex.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.touch_sample_settings()

signals.m2m_changed.connect(touch_sample_settings_m2m, sender=samples_app.UserDetails.my_samples.through)


def touch_sample_settings(sender, instance, **kwargs):
    u"""Touch the “sample settings modified” field in the ``UserDetails``.
    This function is called whenever the ``UserDetails`` of ``chantal_common``
    are changed.  In particular this means that the sample datasheet is not
    taken from the browser cache if the user's preferred language has recently
    changed.
    """
    try:
        instance.user.samples_user_details.touch_sample_settings()
    except samples_app.UserDetails.DoesNotExist:
        # We can safely ignore it.  The initial value of
        # sample_settings_timestamp is correctly set anyway.
        pass

signals.post_save.connect(touch_sample_settings, sender=chantal_common_app.UserDetails)


def add_user_details(sender, instance, **kwargs):
    u"""Create ``UserDetails`` for every newly created user.
    """
    samples_app.UserDetails.objects.get_or_create(user=instance)

signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)


def touch_process_samples(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch samples and processes when the relation between both changes.
    For example, if the samples connected with a process are changed, both the
    process and all affected samples are marked as “modified”.
    """
    if reverse:
        # `instance` is a process
        instance.save()
        if action == "pre_clear":
            for sample in instance.samples.all():
                sample.save()
        elif action in ["post_add", "post_remove"]:
            for sample in samples_app.Sample.objects.in_bulk(pk_set).itervalues():
                sample.save()
    else:
        # `instance` is a sample; shouldn't actually occur in Chantal's code
        instance.save()
        if action == "pre_clear":
            for process in instance.processes.all():
                process.save(with_samples=False)
        elif action in ["post_add", "post_remove"]:
            for process in samples_app.Process.objects.in_bulk(pk_set).itervalues():
                process.save(with_samples=False)

signals.m2m_changed.connect(touch_process_samples, sender=samples_app.Sample.processes.through)
