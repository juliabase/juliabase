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


u"""The samples database app.  This module contains the signal listeners.  Most
of them are for cache expiring, but `expire_feed_entries` cleans up the feed
entries queue.


Caching in Chantal-Samples
==========================

Since this module contains a lot of Chantal-Samples' caching code, it is the
right place to say some general words about it.  It is rather complicated and
scattered over a couple of modules, so it is important to document it
thoroughly.


Goals
.....

We need caching of the most-accessed pages, especially if they are costly to
generate, too.  These are the samples view, the sample series view, and the
main menu page.  We implement a three-level cache:

1. The browser cache.  It is activated with ``last_modified`` functions for all
   three views.  If the page hasn't been modified since the user has last
   accessed it, a 304 (Not Modified) is returned by the server.  We don't use
   ETags for dynamic HTML material.

2. The samples cache.  This is only used for the samples view.  Whole samples
   are stored in the cache as a special data structure called
   ``SamplesAndProcesses``.  In order to increase cache efficiency, this data
   structure can be re-used for different users.  Additionally, it is stored
   multiple times in the cache, for different “display settings” (language,
   skin).  However, it becomes invalid if the sample or some of the displayed
   information is changed.

3. The processes cache.  Every process may be cached so that a sample or sample
   series view may be built from cached items.

These three levels are tried from top to bottom.


Cache invalidation
..................

Of course, the server must never serve outdated data to the user.  In order to
prevent that, every change in the database triggers deletion of those cache
items which have become obsolete.  This is very difficult to achive because
Chantal-Samples contains so many inter-model dependencies (partly indirect).

It may also be possible to compare timestamps in order to detect obsolete cache
items, however, calculating these timestamps is not much easier and required
more work for read accesses, but it is sensible to do as much computation as
possible after write accesses because they occur much more seldomly.

There is no silver bullet for reliable cache invalidation.  On the contrary,
one must go through all models and determine those cached models which are
affected by changes in the first models.  There is not even a good general
strategy for this.  I myself made a big table with paper and pencil.

The best approach is to have in mind the six models that need to be “touched”
in order to delete cache items or to update a last-modified timestamp:

1. ``Sample``.  This contains both a ``last_modified`` timestamp and a list of
   cache items.

2. ``Process``.  The same as with ``Sample``.

3. ``Clearance``.  This contains a ``last_modified``.  ``Clearance`` is very
   low-maintenance: ``last_modified`` is auto-updated whenever the respective
   ``Clearance`` instance is saved, and it doesn't depend on data from any
   other model.

4. ``SampleSeries``.  This contains a ``last_modified``, which is also
   auto-updated whenever the respective series is saved.

5. ``UserDetails``.  This contains a ``display_settings_timestamp`` which is
   the last time the user has changed display settings (language, skin, etc).
   Moreover, it contains ``my_samples_timestamp`` which is the last time the
   user has changed his “My Samples”.

Note that ``SampleSplit`` needs special treatment because it is the only
process which contains sample data (namely the sample's name).  Additionally,
it is the only process the visual representation of which depends on the sample
it is listed with.  The latter is realised by an extended cache key which
contains also the context of the split.

Also note that ``Result`` is special because it can be connected with sample
series.  This way, it may be included into sample data sheets indirectly.  You
see, there's a lot to consider.


Cache invalidation helper methods in ``models_common.py``
.........................................................

A couple of methods have been added to the core models in order to make cache
invalidation more convenient.

First, a couple of models have custom ``save()`` methods which update the
``last_modified`` timestamps.  Some of them have a ``with_relations`` keyword
parameter.  If this is ``True`` (the default), all dependent instances (via
foreign-key or M2M relationships) are touched too.  However normally, the
maximal nesting depth is 1 in order to prevent endless loops.

The special ``save()`` parameters should only be used by other ``save()``
methods or the cache-related signal function in this module.  In particular,
you should not use them in views code.

The same warning applies to the model method ``touch_display_settings``.


Cache invalidation for M2M relationships
........................................

If an M2M relationship changes, no instance in saved.  Thus, we cannot do
proper cache invalidation via ``save()`` methods.  Instead, we use signal
routines in this module.  Additionally, this module contains signal routines
for Django's ``User`` model because we cannot change its ``save()`` method in a
clean way.

Although even many changes which can only be applied through the admin
interface of Django are dealt with in Chantal-Samples' cache invalidation code,
some changes are not.  For example, if you change the name of a sample series,
you must purge the cache manually.  This is done for efficiency reasons.  The
name of a sample series shouldn't change after all, and cannot be changed from
within Chantal-Samples.


Multihop touches
................

In rare cases, the nesting depth of followed relations for cache invalidation
is greater than 1:

``Result`` → ``SampleSeries`` → ``Sample``

``User``/``ExternalOperator`` → ``Process`` → ``Sample``

``User``/``ExternalOperator`` → ``Result`` → ``SampleSeries``
"""


from __future__ import absolute_import

import datetime, hashlib
from django.db.models import signals
import django.contrib.auth.models
from . import models as samples_app
from chantal_common import models as chantal_common_app
from chantal_common.maintenance import maintain


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
    def touch_my_samples(user):
        user_details = user.samples_user_details
        user_details.my_samples_timestamp = datetime.datetime.now()
        user_details.save()
    if reverse:
        # `instance` is ``django.contrib.auth.models.User``
        if action in ["post_add", "post_remove", "post_clear"]:
            touch_my_samples(instance)
    else:
        # `instance` is ``Sample``.
        if action == "pre_clear":
            for user in instance.watchers.all():
                touch_my_samples(user)
        elif action in ["post_add", "post_remove"]:
            for user in django.contrib.auth.models.User.objects.in_bulk(pk_set).itervalues():
                touch_my_samples(user)

signals.m2m_changed.connect(touch_my_samples, sender=samples_app.Sample.watchers.through)


def touch_display_settings(sender, instance, **kwargs):
    u"""Touch the “display settings modified” field in the ``UserDetails``.
    This function is called whenever the ``UserDetails`` of ``chantal_common``
    are changed.  In particular this means that the sample datasheet is not
    taken from the browser cache if the user's preferred language has recently
    changed.
    """
    try:
        if instance.get_data_hash() != instance._old:
            instance.user.samples_user_details.touch_display_settings()
    except samples_app.UserDetails.DoesNotExist:
        # We can safely ignore it.  The initial value of
        # display_settings_timestamp is correctly set anyway.
        pass

signals.post_save.connect(touch_display_settings, sender=chantal_common_app.UserDetails)


def get_identifying_data_hash(user):
    u"""Return the hash of username, firstname, and lastname.  See the
    ``idenfifying_data_hash`` field in ``UserDetails`` for further information.

    :Parameters:
      - `user`: the user

    :type user: ``django.contrib.auth.models.User``

    :Return:
      the SHA1 hash of the identifying data of the user

    :rtype: str
    """
    hash_ = hashlib.sha1()
    hash_.update(user.username)
    hash_.update("\x03")
    hash_.update(user.first_name.encode("utf-8"))
    hash_.update("\x03")
    hash_.update(user.last_name.encode("utf-8"))
    return hash_.hexdigest()


def add_user_details(sender, instance, created, **kwargs):
    u"""Create ``UserDetails`` for every newly created user.
    """
    if created:
        samples_app.UserDetails.objects.get_or_create(user=instance,
                                                      idenfifying_data_hash=get_identifying_data_hash(instance))

signals.post_save.connect(add_user_details, sender=django.contrib.auth.models.User)


def touch_user_samples_and_processes(sender, instance, created, **kwargs):
    u"""Removes all chached items of samples, sample series, and processes
    which are connected with a user.  This is done because the user's name may
    have changed.
    """
    former_identifying_data_hash = get_identifying_data_hash(instance)
    if former_identifying_data_hash != instance.samples_user_details.idenfifying_data_hash:
        instance.samples_user_details.idenfifying_data_hash = former_identifying_data_hash
        instance.samples_user_details.save()
        for sample in instance.samples.all():
            sample.save(with_relations=False)
        for process in instance.processes.all():
            process.actual_instance.save()
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
            for sample_series in instance.sample_series.all():
                sample_series.save(touch_samples=True)
        elif action in ["post_add", "post_remove"]:
            for sample_series in samples_app.SampleSeries.objects.in_bulk(pk_set).itervalues():
                sample_series.save(touch_samples=True)
    else:
        # `instance` is a sample series
        instance.save()

signals.m2m_changed.connect(touch_sample_series_results, sender=samples_app.SampleSeries.results.through)


def touch_display_settings_by_topic(sender, instance, action, reverse, model, pk_set, **kwargs):
    u"""Touch the display settings of all users for which the topics have
    changed because we must invalidate the browser cache for those users (the
    permissions may have changed).
    """
    if reverse:
        # `instance` is a user
        instance.samples_user_details.touch_display_settings()
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
        if action in ["pre_clear", "post_add", "post_remove"]:
            instance.samples_user_details.touch_display_settings()

signals.m2m_changed.connect(touch_display_settings_by_group_or_permission,
                            sender=django.contrib.auth.models.User.groups.through)
signals.m2m_changed.connect(touch_display_settings_by_group_or_permission,
                            sender=django.contrib.auth.models.User.user_permissions.through)


def expire_feed_entries(sender, **kwargs):
    u"""Deletes all feed entries which are older than six weeks.
    """
    now = datetime.datetime.now()
    six_weeks_ago = now - datetime.timedelta(weeks=6)
    for entry in samples_app.FeedEntry.objects.filter(timestamp__lt=six_weeks_ago):
        entry.delete()

maintain.connect(expire_feed_entries, sender=None)
