#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import absolute_import

import datetime
from django.db.models import signals
import django.contrib.auth.models
from . import models as samples_app
from chantal_common import models as chantal_common_app


def touch_my_samples(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch the “My Samples modified” field in the ``UserDetails``.  This
    function is called whenever the “My Samples” of the user change.  It
    assures that when a sample datasheet is displayed next time, it is not
    taken from the browser cache because the “is among My Samples” may be
    outdated otherwise.

    This is only a compromise.  It would be more efficient to expire the
    browser cache only for those samples that have actually changed in “My
    Samples”.  But the gain would be small and the code significantly more
    complex.
    """
    def touch_my_samples(user_details):
        user_details.my_samples_timestamp = datetime.datetime.now()
        user_details.save()
    if reverse:
        # `instance` is ``Sample``.  Shouldn't actually occur in Chantal's
        # code.
        if action == "pre_clear":
            for user_details in instance.watchers.all():
                touch_my_samples(user_details)
        elif action in ["post_add", "post_remove"]:
            for user_details in samples_app.UserDetails.objects.in_bulk(pk_set).itervalues():
                touch_my_samples(user_details)
    else:
        # `instance` is ``UserDetails``
        if action in ["post_add", "post_remove", "post_clear"]:
            touch_my_samples(instance)

signals.m2m_changed.connect(touch_my_samples, sender=samples_app.UserDetails.my_samples.through)


def touch_display_settings(sender, instance, **kwargs):
    u"""Touch the “sample settings modified” field in the ``UserDetails``.
    This function is called whenever the ``UserDetails`` of ``chantal_common``
    are changed.  In particular this means that the sample datasheet is not
    taken from the browser cache if the user's preferred language has recently
    changed.
    """
    try:
        if instance.language != instance._old["language"]:
            instance.user.samples_user_details.touch_display_settings()
    except samples_app.UserDetails.DoesNotExist:
        # We can safely ignore it.  The initial value of
        # display_settings_timestamp is correctly set anyway.
        pass

signals.post_save.connect(touch_display_settings, sender=chantal_common_app.UserDetails)


def add_user_details(sender, instance, created, **kwargs):
    u"""Create ``UserDetails`` for every newly created user.
    """
    if created:
        samples_app.UserDetails.objects.get_or_create(user=instance)

signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)


def touch_user_samples_and_processes(sender, instance, created, **kwargs):
    u"""Removes all chached items of samples, sample series, and processes
    which are connected with a user.  This is done because the user's name may
    have changed.
    """
    for sample in instance.samples.all():
        sample.save(with_relations=False)
    for process in instance.processes.all():
        process.find_actual_instance().save()
    for sample_series in instance.sample_series.all():
        sample_series.save()

signals.post_save.connect(touch_user_samples_and_processes, sender=django.contrib.auth.models.User)


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
                process.save(with_relations=False)
        elif action in ["post_add", "post_remove"]:
            for process in samples_app.Process.objects.in_bulk(pk_set).itervalues():
                process.save(with_relations=False)

signals.m2m_changed.connect(touch_process_samples, sender=samples_app.Sample.processes.through)


def touch_sample_series_samples(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch samples and sample series when the relation between both changes.
    For example, if the members of a sample series are changed, all affected
    samples are marked as “modified”.
    """
    if reverse:
        # `instance` is a sample; shouldn't actually occur in Chantal's code
        instance.save()
        if action == "pre_clear":
            for sample_series in instance.series.all():
                sample_series.save()
        elif action in ["post_add", "post_remove"]:
            for sample_series in samples_app.SampleSeries.objects.in_bulk(pk_set).itervalues():
                sample_series.save()
    else:
        # `instance` is a sample series
        instance.save()
        if action == "pre_clear":
            for sample in instance.samples.all():
                sample.save()
        elif action in ["post_add", "post_remove"]:
            for sample in samples_app.Sample.objects.in_bulk(pk_set).itervalues():
                sample.save()

signals.m2m_changed.connect(touch_sample_series_samples, sender=samples_app.SampleSeries.samples.through)


def touch_sample_series_results(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch sample series when the relation between both changes.  Note that
    we never touch results here because they don't cache information about
    their relationship to series.
    """
    if reverse:
        # `instance` is a result
        if action == "pre_clear":
            for sample_series in instance.series.all():
                sample_series.save(touch_samples=True)
        elif action in ["post_add", "post_remove"]:
            for sample_series in samples_app.SampleSeries.objects.in_bulk(pk_set).itervalues():
                sample_series.save(touch_samples=True)
    else:
        # `instance` is a sample series
        instance.save()

signals.m2m_changed.connect(touch_sample_series_results, sender=samples_app.SampleSeries.results.through)


def touch_display_settings_by_topic(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch the sample settings of all users for which the topics have
    changed because we must invalidate the browser cache for those users (the
    permissions may have changed).
    """
    if reverse:
        # `instance` is a user
        instance.touch_display_settings()
    else:
        # `instance` is a topic
        if action == "pre_clear":
            for user in instance.members.all():
                user.samples_user_details.touch_display_settings()
        elif action in ["post_add", "post_remove"]:
            for user in django.contrib.auth.models.User.objects.in_bulk(pk_set).itervalues():
                user.samples_user_details.touch_display_settings()

signals.m2m_changed.connect(touch_display_settings_by_topic, sender=chantal_common_app.Topic.members.through)


def touch_display_settings_by_group_or_permission(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch the sample settings of all users for which the groups or
    permissions have changed because we must invalidate the browser cache for
    those users.
    """
    if reverse:
        # `instance` is a group or permission
        if action == "pre_clear":
            for user in instance.user_set.all():
                user.samples_user_details.touch_display_settings()
        elif action in ["post_add", "post_remove"]:
            for user in django.contrib.auth.models.User.objects.in_bulk(pk_set).itervalues():
                user.samples_user_details.touch_display_settings()
    else:
        # `instance` is a user
        instance.touch_display_settings()

signals.m2m_changed.connect(touch_display_settings_by_group_or_permission,
                            sender=django.contrib.auth.models.User.groups.through)
signals.m2m_changed.connect(touch_display_settings_by_group_or_permission,
                            sender=django.contrib.auth.models.User.user_permissions.through)
