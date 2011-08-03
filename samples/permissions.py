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


u"""Central permission checking.  This module consists of three parts: First,
the exception that is raised if a certain permission condition is not met.
Secondly, the assertion functions that test for certain permissions.  And
thirdly, top-level code that generates a ``has_permission_to_...`` function for
every ``assert_can_...`` function.

The idea is the following.  For example, there is a function called
``assert_can_fully_view_sample``.  If the user can't view the sample, a
``PermissionError`` is raised.  Sometimes however, you just want to check it
without having to catch an exception.  Then, you use
``has_permission_to_fully_view_sample``.  The parameters are the same but
instead of raising an exception, it returns ``True`` or ``False``.

The ``assert_can_...`` function are typically used at the beginning of views
where permissions need to be checked and every failure means an error.  By
contrast, the ``has_permission_to_...`` functions are used where a missing
permission just means that e.g. a link is not generated (for example, in the
``get_context_for_user`` methods in the models).
"""

from __future__ import absolute_import

import hashlib
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy
import django.contrib.auth.models
from django.conf import settings
from settings import WITH_EPYDOC
if not WITH_EPYDOC:
    # Attention! This is a cyclic import.  Don't use models in top-level code.
    import samples.models
from chantal_common.models import Topic
from chantal_common import utils as chantal_common_utils
from samples.views import shared_utils


def translate_permission(permission_codename):
    u"""Translates a permission description to the user's language.

    :Parameters:
      - `permission_codename`: the codename of the permission, *with* the
        ``"all_label."`` prefix

    :type permission_codename: str

    :Return:
      The name (aka short description) of the permission, translated to the
      current langauge.  It starts with a capital letter but doesn't end in a
      full stop.

    :rtype: unicode
    """
    permission_codename = permission_codename.partition(".")[2]
    try:
        return ugettext(django.contrib.auth.models.Permission.objects.get(codename=permission_codename).name)
    except django.contrib.auth.models.Permission.DoesNotExist:
        return _(u"[not available]")


def get_user_permissions(user):
    u"""Determines the permissions of a user.  It iterates through all
    permissions and looks whether the user has them or not, and returns its
    findings.

    :Parameters:
      - `user`: the user for which the permissions should be determined

    :type user: ``django.contrib.auth.models.User``

    :Return:
      A list with all permissions the user has got, a list with all permissions
      that the user doesn't have got.  Both lists contain translated
      descriptions.

    :rtype: list of unicode, list of unicode
    """
    has = []
    has_not = []
    for permission in django.contrib.auth.models.Permission.objects.all():
        if not issubclass(permission.content_type.model_class(), samples.models.PhysicalProcess):
            full_permission_name = permission.content_type.app_label + "." + permission.codename
            if user.has_perm(full_permission_name):
                has.append(ugettext(permission.name))
            else:
                has_not.append(ugettext(permission.name))
    return has, has_not


def get_user_hash(user):
    u"""Generates a secret hash that is connected with a user.  It is means as
    some sort of URL-based login for fetching feeds.  If the user accesses his
    feed via his aggregator, he is possibly not logged-in.  Because the
    aggregator cannot login by itself, the URL must be made unguessable.  This
    is done by appending the secret hash.

    Technically, it is the first 10 characters of a salted SHA-1 hash of the
    user's name.

    :Parameters:
      - `user`: the current user

    :type user: ``django.contrib.auth.models.User``

    :Return:
      The user's secret hash

    :rtype: str
    """
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY)
    user_hash.update(user.username)
    return user_hash.hexdigest()[:10]


def get_editable_sample_series(user):
    u"""Return a query set with all sample series that the user can edit.  So
    far, it is only used in `split_and_rename.GlobalDataForm`.

    :Parameters:
      - `user`: the user which has too few permissions

    :type user: ``django.contrib.auth.models.User``

    :Return:
      a query set with all sample series that the user can edit

    :rtype: ``QuerySet``
    """
    return samples.models.SampleSeries.objects.filter(currently_responsible_person=user)


all_addable_physical_process_models = None
def get_all_addable_physical_process_models():
    u"""Get all physical process classes (depositions, measurements; no sample
    splits) that one can add or edit.  Never call this routine from top-level
    module code because it may cause cyclic imports.

    :Return:
      Dictionary mapping all physical processes one can to add.  Every process
      class is mapped to a dictionary with three keys, namely ``"url"`` with
      the url to the “add” view for the process, ``"label"`` with the name of
      the process (starting lowercase), and ``"type"`` with the process'
      class name.

    :rtype: dict mapping class to dict mapping str to unicode
    """
    global all_addable_physical_process_models
    if all_addable_physical_process_models is None:
        all_addable_physical_process_models = {}
        for process_class in chantal_common_utils.get_all_models().itervalues():
            if issubclass(process_class, samples.models.PhysicalProcess):
                try:
                    url = process_class.get_add_link()
                except NotImplementedError, AttributeError:
                    continue
                all_addable_physical_process_models[process_class] = {
                    "url": process_class.get_add_link(), "label": process_class._meta.verbose_name,
                    "label_plural": process_class._meta.verbose_name_plural, "type": process_class.__name__}
    return all_addable_physical_process_models


def get_allowed_physical_processes(user):
    u"""Get a list with all physical process classes (depositions, measurements;
    no sample splits) that the user is allowed to add or edit.  This routine is
    typically used where a list of all processes that the user is allowed to
    *add* is to be build, on the main menu page and the “add process to sample”
    page.

    :Parameters:
      - `user`: the user whose allowed physical processes should be collected

    :type user: ``django.contrib.auth.models.User``

    :Return:
      List of all physical processes the user is allowed to add to the
      database.  Every process is represented by a dictionary with three keys,
      namely ``"url"`` with the url to the “add” view for the process,
      ``"label"`` with the name of the process (starting lowercase), and
      ``"type"`` with the process' class name.

    :rtype: list of dict mapping str to unicode
    """
    allowed_physical_processes = []
    for physical_process_class, add_data in get_all_addable_physical_process_models().iteritems():
        if has_permission_to_add_physical_process(user, physical_process_class):
            allowed_physical_processes.append(add_data.copy())
    allowed_physical_processes.sort(key=lambda process: process["label"].lower())
    return allowed_physical_processes


class PermissionError(Exception):
    u"""Common class for all permission exceptions.

    :ivar description: the full description of the problem, possible remedy
      inclusive.  It should be a complete sentence, which addresses the user
      directly.  It should start with a capital letter and end with a full
      stop.  For example, it may be “You are not allowed to view sample 01B-410
      because you're not … Note that a head of an institute topic may add you
      to new topics.”.

    :type description: unicode
    """

    def __init__(self, user, description, new_topic_would_help=False):
        u"""Class constructor.

        :Parameters:
          - `user`: the user which has too few permissions
          - `description`: a sentence describing the denied action and what
            could be done about it
          - `new_topic_would_help`: if ``True``, adding the user to a certain
            topic would grant him the permission for the action

        :type user: ``django.contrib.auth.models.User``
        :type description: unicode
        :type new_topic_would_help: bool
        """
        super(PermissionError, self).__init__(_(u"Permission denied: ") + description)
        self.user, self.description, self.new_topic_would_help = user, description, new_topic_would_help


def assert_can_fully_view_sample(user, sample):
    u"""Tests whether the user can view the sample fully, i.e. without needing
    a clearance.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample`: the sample to be shown

    :type user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to fully view the
        sample.
    """
    currently_responsible_person = sample.currently_responsible_person
    if sample.topic and sample.topic not in user.topics.all() and currently_responsible_person != user and \
            not user.is_superuser:
        if sample.topic.confidential:
            description = _(u"You are not allowed to view the sample since you are not in the sample's topic, nor are you "
                            u"its currently responsible person ({name})."). \
                            format(name=chantal_common_utils.get_really_full_name(currently_responsible_person))
            raise PermissionError(user, description, new_topic_would_help=True)
        elif not user.has_perm("samples.view_all_samples"):
            description = _(u"You are not allowed to view the sample since you are not in the sample's topic, nor are you "
                            u"its currently responsible person ({name}), nor can you view all samples."). \
                            format(name=chantal_common_utils.get_really_full_name(currently_responsible_person))
            raise PermissionError(user, description, new_topic_would_help=True)


def get_sample_clearance(user, sample):
    u"""Returns the clearance a user needs to visit a sample, if he needs one
    at all.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample`: the sample to be shown

    :type user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`

    :Return:
      the clearance for the user and sample, or ``None`` if the user doesn't
      need a clearance to visit the sample

    :rtype: `samples.models.Clearance` or ``NoneType``

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the
        sample.
    """
    clearance = None
    try:
        assert_can_fully_view_sample(user, sample)
    except PermissionError as error:
        try:
            clearance = samples.models.Clearance.objects.get(user=user, sample=sample)
        except samples.models.Clearance.DoesNotExist:
            raise error
    return clearance


def assert_can_add_physical_process(user, process_class):
    u"""Tests whether the user can create a new physical process
    (i.e. deposition, measurement, etching process, clean room work etc).

    :Parameters:
      - `user`: the user whose permission should be checked
      - `process_class`: the type of physical process that the user asks
        permission for

    :type user: ``django.contrib.auth.models.User``
    :type process_class: ``class`` (derived from `models.Process`)

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to add a process.
    """
    codename = "add_{0}".format(shared_utils.camel_case_to_underscores(process_class.__name__))
    if django.contrib.auth.models.Permission.objects.filter(codename=codename).exists():
        permission = "{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename)
        if not user.has_perm(permission):
            description = _(u"You are not allowed to add {process_plural_name} because you don't have the "
                            u"permission “{permission}”.").format(
                process_plural_name=process_class._meta.verbose_name_plural, permission=translate_permission(permission))
            raise PermissionError(user, description)


def assert_can_edit_physical_process(user, process):
    u"""Tests whether the user can edit a physical process (i.e. deposition,
    measurement, etching process, clean room work etc).  For this, he must be
    the operator of this process, *and* he must be allowed to add new processes
    of this kind.  Alternatively, he must have the “edit all” permission for
    the process class.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `process`: The process to edit.  This neend't be the actual instance.

    :type user: ``django.contrib.auth.models.User``
    :type process: `models.Process`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit the
        process.
    """
    process_class = process.content_type.model_class()
    codename = "edit_every_{0}".format(shared_utils.camel_case_to_underscores(process_class.__name__))
    has_edit_all_permission = \
        user.has_perm("{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename))
    codename = "add_{0}".format(shared_utils.camel_case_to_underscores(process_class.__name__))
    if django.contrib.auth.models.Permission.objects.filter(codename=codename).exists():
        has_add_permission = \
            user.has_perm("{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename))
    else:
        has_add_permission = True
    if (not has_add_permission or process.operator != user) and not (has_add_permission and not process.finished) and \
            not has_edit_all_permission and not user.is_superuser:
        description = _(u"You are not allowed to edit the process “{process}” because you are not the operator "
                        u"of this process.").format(process=process)
        raise PermissionError(user, description)


def assert_can_add_edit_physical_process(user, process, process_class=None):
    u"""Tests whether the user can create or edit a physical process
    (i.e. deposition, measurement, etching process, clean room work etc).  This
    is a convenience function which combines `assert_can_add_physical_process`
    and `assert_can_edit_physical_process`.  It is used in the combined
    add/edit views of physical processes.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `process`: The concrete process to edit.  If ``None``, a new process is
        about to be created.
      - `process_class`: the type of physical process that the user asks
        permission for

    :type user: ``django.contrib.auth.models.User``
    :type process: `models.Process`
    :type process_class: ``class`` (derived from `models.Process`) or
      ``NoneType``

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to create or edit
        the process.
    """
    if process:
        assert process_class == process.__class__
        assert_can_edit_physical_process(user, process)
    else:
        assert_can_add_physical_process(user, process_class)


def assert_can_view_lab_notebook(user, process_class):
    u"""Tests whether the user can view the lab notebook for a physical process
    class (i.e. deposition, measurement, etching process, clean room work etc).

    :Parameters:
      - `user`: the user whose permission should be checked
      - `process_class`: the type of physical process that the user asks
        permission for

    :type user: ``django.contrib.auth.models.User``
    :type process_class: ``class`` (derived from `models.Process`)

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the lab
        notebook for this process class.
    """
    codename = "view_every_{0}".format(shared_utils.camel_case_to_underscores(process_class.__name__))
    permission_name_to_view_all = "{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename)
    if django.contrib.auth.models.Permission.objects.filter(codename=codename).exists():
        has_view_all_permission = user.has_perm(permission_name_to_view_all)
    else:
        has_view_all_permission = user.is_superuser
    if not has_view_all_permission:
        description = _(u"You are not allowed to view lab notebooks for {process_plural_name} because you don't have the "
                        u"permission “{permission}”.").format(
            process_plural_name=process_class._meta.verbose_name_plural,
            permission=translate_permission(permission_name_to_view_all))
        raise PermissionError(user, description)

def assert_can_view_physical_process(user, process):
    u"""Tests whether the user can view a physical process (i.e. deposition,
    measurement, etching process, clean room work etc).  You can view a process
    if you can view all such processes, if you can add such processes and you
    are the operator of this process, if you have a clearance for this process,
    or if you can see at least one of the processed samples.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `process`: The concrete process to view.  It it not necessary that it
        is the actual instance, i.e. it may also be a ``Process`` instance.

    :type user: ``django.contrib.auth.models.User``
    :type process: `models.Process`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the
        process.
    """
    process_class = process.content_type.model_class()
    codename = "add_{0}".format(shared_utils.camel_case_to_underscores(process_class.__name__))
    if django.contrib.auth.models.Permission.objects.filter(codename=codename).exists():
        has_add_permission = user.has_perm("{app_label}.{codename}".format(
                app_label=process_class._meta.app_label, codename=codename))
    else:
        has_add_permission = True
    codename = "view_every_{0}".format(shared_utils.camel_case_to_underscores(process_class.__name__))
    permission_name_to_view_all = "{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename)
    if django.contrib.auth.models.Permission.objects.filter(codename=codename).exists():
        has_view_all_permission = user.has_perm(permission_name_to_view_all)
    else:
        has_view_all_permission = user.is_superuser
    if not has_view_all_permission and not (has_add_permission and process.operator == user) and \
            not any(has_permission_to_fully_view_sample(user, sample) for sample in process.samples.all()):
        if not samples.models.Clearance.objects.filter(user=user, processes=process).exists():
            description = _(u"You are not allowed to view the process “{process}” because neither you have the "
                            u"permission “{permission}”, nor you are allowed to view one of the processed samples, "
                            "nor is there a clearance for you for this process.").format(
                process=process, permission=translate_permission(permission_name_to_view_all))
            raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_edit_result_process(user, result_process):
    u"""Tests whether the user can edit a result process.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `result_process`: The result process to edit.

    :type user: ``django.contrib.auth.models.User``
    :type result_process: `models.Result`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit the result
        process.
    """
    if result_process.operator != user and not user.is_superuser:
        description = _(u"You are not allowed to edit the result “{result}” because you didn't create this result.").format(
            result=result_process)
        raise PermissionError(user, description)


def assert_can_view_result_process(user, result_process):
    u"""Tests whether the user can view a result process.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `result_process`: The result process to edit.

    :type user: ``django.contrib.auth.models.User``
    :type result_process: `models.Result`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the result
        process.
    """
    if result_process.operator != user and \
            all(not has_permission_to_fully_view_sample(user, sample) for sample in result_process.samples.all()) and \
            all(not has_permission_to_fully_view_sample_series(user, sample_series)
                for sample_series in result_process.sample_series.all()) and \
                not samples.models.Clearance.objects.filter(user=user, processes=result_process).exists():
        description = _(u"You are not allowed to view the result “{result}” because neither did you create this result, "
                        u"nor are you allowed to view its connected samples or sample series, nor is there a "
                        "clearance for you for this result.").format(result=result_process)
        raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_add_result_process(user, sample_or_series):
    u"""Tests whether the user can add a result process.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample_or_series`: the sample (series) the user wants to add a result
        to

    :type user: ``django.contrib.auth.models.User``
    :type sample_or_series: `models.Sample` or `models.SampleSeries`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to add the result
        process to the sample or series
    """
    if sample_or_series.currently_responsible_person != user and sample_or_series.topic and \
            sample_or_series.topic not in user.topics.all() and not user.is_superuser:
        if isinstance(sample_or_series, samples.models.Sample):
            description = _(u"You are not allowed to add the result to {sample_or_series} because neither are you the "
                            u"currently responsible person for this sample, nor are you a member of its topic.").format(
                sample_or_series=sample_or_series)
        else:
            description = _(u"You are not allowed to add the result to {sample_or_series} because neither are you the "
                            u"currently responsible person for this sample series, nor are you a member of its "
                            u"topic.").format(sample_or_series=sample_or_series)
        raise PermissionError(user, description)


def assert_can_edit_sample(user, sample):
    u"""Tests whether the user can edit, split, and kill a sample.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample`: the sample to be changed

    :type user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit the sample
    """
    if sample.topic and sample.currently_responsible_person != user and not user.is_superuser:
        description = _(u"You are not allowed to edit the sample “{name}” (including splitting and declaring dead) because "
                        u"you are not the currently responsible person for this sample.").format(name=sample)
        raise PermissionError(user, description)


def assert_can_edit_sample_series(user, sample_series):
    u"""Tests whether the user can edit a sample series, including adding or
    removing samples.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample_series`: the sample series to be changed

    :type user: ``django.contrib.auth.models.User``
    :type sample_series: `models.SampleSeries`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit the sample
        series
    """
    if sample_series.currently_responsible_person != user and not user.is_superuser:
        description = _(u"You are not allowed to edit the sample series “{name}” because "
                        u"you are not the currently responsible person for this sample series.").format(name=sample_series)
        raise PermissionError(user, description)


def assert_can_view_sample_series(user, sample_series):
    u"""Tests whether the user can view a sample series.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample_series`: the sample series to be shown

    :type user: ``django.contrib.auth.models.User``
    :type sample_series: `models.SampleSeries`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the sample
        series
    """
    if sample_series.currently_responsible_person != user and sample_series.topic not in user.topics.all() and \
            not user.is_superuser:
        description = _(u"You are not allowed to view the sample series “{name}” because neither are "
                        u"you the currently responsible person for it, nor are you in its topic.").format(name=sample_series)
        raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_add_external_operator(user):
    u"""Tests whether the user can add an external operator.

    :Parameters:
      - `user`: the user whose permission should be checked

    :type user: ``django.contrib.auth.models.User``

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to add an external
        operator.
    """
    permission = "samples.add_external_operator"
    if not user.has_perm(permission):
        description = _(u"You are not allowed to add an external operator because you don't have the permission “{name}”.") \
            .format(name=translate_permission(permission))
        raise PermissionError(user, description)


def assert_can_edit_external_operator(user, external_operator):
    u"""Tests whether the user can edit an external operator.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `external_operator`: the external operator to be edited

    :type user: ``django.contrib.auth.models.User``
    :type external_operator: `models.ExternalOperator`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit an
        external operator.
    """
    if external_operator.contact_person != user and not user.is_superuser:
        description = _(u"You are not allowed to edit this external operator because you aren't their "
                        u"current contact person.")
        raise PermissionError(user, description)


def assert_can_view_external_operator(user, external_operator):
    u"""Tests whether the user can view an external operator.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `external_operator`: the external operator to be shown

    :type user: ``django.contrib.auth.models.User``
    :type external_operator: `models.ExternalOperator`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view an
        external operator.
    """
    if external_operator.contact_person != user and not user.is_superuser:
        if external_operator.confidential:
            description = _(u"You are not allowed to view this external operator because you are not their "
                            u"current contact person.")
            raise PermissionError(user, description)
        elif not user.has_perm("samples.view_all_external_operators"):
            description = _(u"You are not allowed to view this external operator because neither are you their "
                            u"current contact person, nor can you view all external operators.")
            raise PermissionError(user, description)


def assert_can_edit_topic(user, topic=None):
    u"""Tests whether the user can change topic memberships of other users,
    set the topic's restriction status, and add new topics.  This typically
    is a priviledge of heads of institute topics.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `topic`: the topic whose members are about to be edited; ``None``
        if we create a new one, list topics etc

    :type user: ``django.contrib.auth.models.User``
    :type topic: ``chantal_common.models.Topic`` or ``NoneType``

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit topics,
        or to add new topics.
    """
    if not topic:
        if not user.has_perm("chantal_common.can_edit_all_topics"):
            description = _(u"You are not allowed to add or list topics because you don't have the permission “{name}”.") \
                .format(name=translate_permission("chantal_common.can_edit_all_topics"))
            raise PermissionError(user, description)
    else:
        if user in topic.members.all():
            if not user.has_perm("chantal_common.can_edit_all_topics") and \
                    not user.has_perm("chantal_common.can_edit_their_topics"):
                description = _(u"You are not allowed to change this topic because you don't have the permission "
                                u"“{0}” or “{1}”.").format(translate_permission("chantal_common.can_edit_all_topics"),
                                                           translate_permission("chantal_common.can_edit_their_topics"))
                raise PermissionError(user, description)
        else:
            if not user.has_perm("chantal_common.can_edit_all_topics"):
                description = _(u"You are not allowed to change this topic because "
                                u"you don't have the permission “{name}”.").format(
                    name=translate_permission("chantal_common.can_edit_all_topics"))
                raise PermissionError(user, description)
            elif topic.confidential and not user.is_superuser:
                description = _(u"You are not allowed to change this topic because it is confidential "
                                u"and you are not in this topic.")
                raise PermissionError(user, description)


def assert_can_view_feed(hash_value, user):
    u"""Tests whether the requester that gave a certain ``hash_value`` can view
    the news feed of a certain ``user``.  Basically, this tests whether the
    requester *is* the user because only he can know the hash value.

    Note that additionally, I have to test here whether the feed's user is
    still active because you needn't be logged-in to access a feed, and I don't
    use any ``has_perm`` method call here (which would yield ``False`` for
    inactive users).

    :Parameters:
      - `hash_value`: the hash value given by the requester
      - `user`: the user whose news feed is requested

    :type hash_value: str
    :type user: ``django.contrib.auth.models.User``

    :Exceptions:
      - `PermissionError`: Raised if the requester is not allowed to view the
        user's news feed.  It's ``user`` parameter is always ``None`` because
        we don't know the user who is currently accessing Chantal.
    """
    if not user.is_superuser:
        if hash_value != get_user_hash(user):
            description = _(u"You gave an invalid hash parameter in the query string.  "
                            u"Note that you can't access the news feed of another user.")
            raise PermissionError(None, description)
        if not user.is_active:
            description = _(u"You can't access the feed of an inactive user.")
            raise PermissionError(None, description)


# Now, I inject the ``has_permission_to_...`` functions into this module for
# for every ``assert_can_...`` function found here.

def generate_permission_function(assert_func):
    def has_permission(*args, **kwargs):
        try:
            assert_func(*args, **kwargs)
        except PermissionError:
            return False
        else:
            return True
    return has_permission


import copy, inspect
_globals = copy.copy(globals())
all_assertion_functions = [func for func in _globals.values()
                           if inspect.isfunction(func) and func.__name__.startswith("assert_can_")]
for func in all_assertion_functions:
    new_name = "has_permission_to_" + func.__name__[len("assert_can_"):]
    globals()[new_name] = generate_permission_function(func)
