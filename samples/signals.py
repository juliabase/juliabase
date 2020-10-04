# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""The samples database app.  This module contains the signal listeners.  Most
of them are for cache expiring, but `expire_feed_entries` cleans up the feed
entries queue.


Caching in JuliaBase-Samples
============================

Since this module contains a lot of JuliaBase-Samples' caching code, it is the
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
   accessed it, a 304 (Not Modified) is returned by the server.  Additionally,
   we generate ETags because some browsers ignore "Vary: Cookie" and show a
   cached page to a different user.

2. The samples cache.  This is only used for the samples view.  Whole samples
   are stored in the cache as a special data structure called
   :py:class:`~samples.views.sample.SamplesAndProcesses`.  In order to increase
   cache efficiency, this data structure can be re-used for different users.
   Additionally, it is stored multiple times in the cache, for different
   “layout settings” (language, skin).  However, it becomes invalid if the
   sample or some of the displayed information is changed.

3. The processes cache.  Every process may be cached so that a sample or sample
   series view may be built from cached items.

These three levels are tried from top to bottom.


Cache invalidation
..................

Of course, the server must never serve outdated data to the user.  In order to
prevent that, every change in the database triggers deletion of those cache
items which have become obsolete.  This is very difficult to achive because
JuliaBase-Samples contains so many inter-model dependencies (partly indirect).

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
   the last time the user has changed things that affect display of samples and
   sample series (topic memberships, clearances, etc).  Moreover, it contains
   ``my_samples_timestamp`` which is the last time the user has changed his “My
   Samples”.

   Additionally, the ``UserDetails`` of ``jb_common`` contain the field
   ``layout_last_modified`` which is updated when language or browser are
   changed (this also affects display of samples and sample series).

Note that ``SampleSplit`` needs special treatment because it is the only
process which contains sample data (namely the sample's name).  Additionally,
it is the only process the visual representation of which depends on the sample
it is listed with.  The latter is realised by an extended cache key which
contains also the context of the split.

Also note that ``Result`` is special because it can be connected with sample
series.  This way, it may be included into sample data sheets indirectly.  You
see, there's a lot to consider.


Cache invalidation helper methods in ``models/common.py``
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
interface of Django are dealt with in JuliaBase-Samples' cache invalidation
code, some changes are not.  For example, if you change the name of a sample
series, you must purge the cache manually.  This is done for efficiency
reasons.  The name of a sample series shouldn't change after all, and cannot be
changed from within JuliaBase-Samples.


Multihop touches
................

In rare cases, the nesting depth of followed relations for cache invalidation
is greater than 1:

``Result`` → ``SampleSeries`` → ``Sample``

``User``/``ExternalOperator`` → ``Process`` → ``Sample``

``User``/``ExternalOperator`` → ``Result`` → ``SampleSeries``
"""


import datetime, hashlib
from django.db.models import signals
import django.utils.timezone
from django.dispatch import receiver
from django.contrib.auth.models import User
import django.contrib.contenttypes.management
from django.contrib.contenttypes.models import ContentType
from jb_common import models as jb_common_app
import jb_common.signals
from samples import models as samples_app


@receiver(signals.m2m_changed, sender=samples_app.Sample.watchers.through)
def touch_my_samples(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Touch the “My Samples modified” field in the ``UserDetails``.  This
    function is called whenever the “My Samples” of the user change.  It
    assures that when a sample datasheet is displayed next time, it is not
    taken from the browser cache because the “is among My Samples” may be
    outdated otherwise.

    This is only a compromise.  It would be more efficient to expire the
    browser cache only for those samples that have actually changed in “My
    Samples”.  But the gain would be small and the code significantly more
    complex.
    """
    now = django.utils.timezone.now()
    if reverse:
        # `instance` is django.contrib.auth.models.User
        if action in ["post_add", "post_remove", "post_clear"]:
            user_details = instance.samples_user_details
            user_details.my_samples_timestamp = user_details.my_samples_list_timestamp = now
            user_details.save()
    else:
        # `instance` is ``Sample``.
        if action == "pre_clear":
            samples_app.UserDetails.objects.filter(user__in=instance.watchers.all()).update(
                my_samples_timestamp=now, my_samples_list_timestamp=now)
        elif action in ["post_add", "post_remove"]:
            samples_app.UserDetails.objects.filter(user__pk__in=pk_set).update(
                my_samples_timestamp=now, my_samples_list_timestamp=now)



def get_identifying_data_hash(user):
    """Return the hash of username, firstname, and lastname.  See the
    :py:attr:`samples.models.UserDetails.identifying_data_hash` field for
    further information.

    :param user: the user

    :type user: django.contrib.auth.models.User

    :return:
      the SHA1 hash of the identifying data of the user

    :rtype: str
    """
    hash_ = hashlib.sha1()
    hash_.update(user.username.encode())
    hash_.update(b"\x03")
    hash_.update(user.first_name.encode())
    hash_.update(b"\x03")
    hash_.update(user.last_name.encode())
    return hash_.hexdigest()


@receiver(signals.post_save, sender=User)
def add_user_details(sender, instance, created=True, **kwargs):
    """Create ``UserDetails`` for every newly created user.
    """
    # This routine is slightly problematic because we depend on fully ready
    # contenttypes and existing jb_common.UserDetails.  Since we cannot rely on
    # the calling order, and have to trigger the respective initialisers
    # ourselves if necessary.
    def set_subscribed_feeds(user_details):
        user_details.subscribed_feeds.set([ContentType.objects.get(app_label="samples", model="sample"),
                                           ContentType.objects.get(app_label="samples", model="sampleseries"),
                                           ContentType.objects.get(app_label="jb_common", model="topic")])
    if created:
        user_details = samples_app.UserDetails.objects.create(
            user=instance, identifying_data_hash=get_identifying_data_hash(instance))
        try:
            set_subscribed_feeds(user_details)
        except ContentType.DoesNotExist:
            # This can happen only during the initial migration.
            django.contrib.contenttypes.management.update_all_contenttypes()
            set_subscribed_feeds(user_details)

        try:
            department = instance.jb_user_details.department
        except jb_common_app.UserDetails.DoesNotExist:
            jb_common.signals.add_user_details(User, instance, created=True)
            department = instance.jb_user_details.department
        if department:
            user_details.show_users_from_departments.set([department])

        user_details.save()


@receiver(signals.post_migrate)
def add_all_user_details(sender, **kwargs):
    """Create ``UserDetails`` for all users where necessary.  This is needed
    because during data migrations, no signals are sent.
    """
    for user in User.objects.filter(samples_user_details=None):
        add_user_details(User, user, created=True)


@receiver(signals.post_save, sender=User)
def touch_user_samples_and_processes(sender, instance, created, **kwargs):
    """Removes all cached items of samples, sample series, and processes which
    are connected with a user.  This is done because the user's name may have
    changed.
    """
    former_identifying_data_hash = get_identifying_data_hash(instance)
    if former_identifying_data_hash != instance.samples_user_details.identifying_data_hash:
        instance.samples_user_details.identifying_data_hash = former_identifying_data_hash
        instance.samples_user_details.save()
        for sample in instance.samples.all():
            sample.save(with_relations=False)
        for process in instance.processes.all():
            process.actual_instance.save()
        for sample_series in instance.sample_series.all():
            sample_series.save()


@receiver(signals.m2m_changed, sender=samples_app.Sample.processes.through)
def touch_process_samples(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Touch samples and processes when the relation between both changes.
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
            for sample in samples_app.Sample.objects.in_bulk(pk_set).values():
                sample.save()
    else:
        # `instance` is a sample; shouldn't actually occur in JuliaBase's code
        instance.save()
        if action == "pre_clear":
            for process in instance.processes.all():
                process.save(with_relations=False)
        elif action in ["post_add", "post_remove"]:
            for process in samples_app.Process.objects.in_bulk(pk_set).values():
                process.save(with_relations=False)


@receiver(signals.m2m_changed, sender=samples_app.SampleSeries.samples.through)
def touch_sample_series_samples(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Touch samples and sample series when the relation between both changes.
    For example, if the members of a sample series are changed, all affected
    samples are marked as “modified”.
    """
    if reverse:
        # `instance` is a sample; shouldn't actually occur in JuliaBase's code
        instance.save()
        if action == "pre_clear":
            for sample_series in instance.series.all():
                sample_series.save()
        elif action in ["post_add", "post_remove"]:
            for sample_series in samples_app.SampleSeries.objects.in_bulk(pk_set).values():
                sample_series.save()
    else:
        # `instance` is a sample series
        instance.save()
        if action == "pre_clear":
            for sample in instance.samples.all():
                sample.save()
        elif action in ["post_add", "post_remove"]:
            for sample in samples_app.Sample.objects.in_bulk(pk_set).values():
                sample.save()


@receiver(signals.m2m_changed, sender=samples_app.SampleSeries.results.through)
def touch_sample_series_results(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Touch sample series when the relation between both changes.  Note that
    we never touch results here because they don't cache information about
    their relationship to series.
    """
    if reverse:
        # `instance` is a result
        if action == "pre_clear":
            for sample_series in instance.sample_series.all():
                sample_series.save(touch_samples=True)
        elif action in ["post_add", "post_remove"]:
            for sample_series in samples_app.SampleSeries.objects.in_bulk(pk_set).values():
                sample_series.save(touch_samples=True)
    else:
        # `instance` is a sample series
        instance.save()


@receiver(signals.pre_save, sender=jb_common_app.Topic)
def touch_my_samples_list_by_topic(sender, instance, raw, **kwargs):
    """Considers the “My Samples” lists of *all* users as changed if the topic has
    changed its “confidential” status, so its name may appear differently on
    the “My Samples” lists.

    Note this is may be called redundantly multiple times in case of subtopics.
    This is unfortunate but difficult to fix – we don't know whether we are in
    the genuine ``save()`` call.  However, it should not be too costly either,
    and topics are changed seldomly.
    """
    if not raw and instance.pk:
        old_instance = jb_common_app.Topic.objects.get(pk=instance.pk)
        if old_instance.name != instance.name or old_instance.confidential != instance.confidential:
            samples_app.UserDetails.objects.update(my_samples_list_timestamp=django.utils.timezone.now())


@receiver(signals.m2m_changed, sender=jb_common_app.Topic.members.through)
def touch_my_samples_list_by_topic_memberships(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Considers the “My Samples” lists of such users as changed if the topic is
    confidential because then, the topic's appearance in the “My Samples” list
    changes.
    """
    # FixMe: This also affects users whose topic memberships haven't changed
    # but who just happen to be in a topic the memberships of which has
    # changed.  Could be possibly fixed by not assigning just a list to
    # ``topic.members`` in the "edit topic" view.
    now = django.utils.timezone.now()
    if reverse:
        # `instance` is a user
        user_details = instance.samples_user_details
        user_details.my_samples_list_timestamp = now
        user_details.save()
    else:
        # `instance` is a topic
        if instance.confidential:
            if action == "pre_clear":
                samples_app.UserDetails.objects.filter(user__in=instance.members.all()).update(my_samples_list_timestamp=now)
            elif action in ["post_add", "post_remove"]:
                samples_app.UserDetails.objects.filter(user__pk__in=pk_set).update(my_samples_list_timestamp=now)


@receiver(signals.m2m_changed, sender=jb_common_app.Topic.members.through)
def touch_display_settings_by_topic(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Touch the display settings of all users for which the topics have
    changed because we must invalidate the browser cache for those users (the
    permissions may have changed).
    """
    # FixMe: This also affects users whose topic memberships haven't changed
    # but who just happen to be in a topic the memberships of which has
    # changed.  Could be possibly fixed by not assigning just a list to
    # ``topic.members`` in the "edit topic" view.
    if reverse:
        # `instance` is a user
        instance.samples_user_details.touch_display_settings()
    else:
        # `instance` is a topic
        if action == "pre_clear":
            for user in instance.members.all():
                user.samples_user_details.touch_display_settings()
        elif action in ["post_add", "post_remove"]:
            for user in User.objects.in_bulk(pk_set).values():
                user.samples_user_details.touch_display_settings()


@receiver(signals.m2m_changed, sender=User.groups.through)
@receiver(signals.m2m_changed, sender=User.user_permissions.through)
def touch_display_settings_by_group_or_permission(sender, instance, action, reverse, model, pk_set, **kwargs):
    """Touch the sample settings of all users for which the groups or
    permissions have changed because we must invalidate the browser cache for
    those users.
    """
    if reverse:
        # `instance` is a group or permission
        if action == "pre_clear":
            for user in instance.user_set.all():
                user.samples_user_details.touch_display_settings()
        elif action in ["post_add", "post_remove"]:
            for user in User.objects.in_bulk(pk_set).values():
                user.samples_user_details.touch_display_settings()
    else:
        # `instance` is a user
        if action in ["pre_clear", "post_add", "post_remove"]:
            instance.samples_user_details.touch_display_settings()


@receiver(jb_common.signals.maintain)
def expire_feed_entries(sender, **kwargs):
    """Deletes all feed entries which are older than six weeks.
    """
    now = django.utils.timezone.now()
    six_weeks_ago = now - datetime.timedelta(weeks=6)
    samples_app.FeedEntry.objects.filter(timestamp__lt=six_weeks_ago).delete()
