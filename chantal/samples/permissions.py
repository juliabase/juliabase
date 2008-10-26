#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Central permission checking.  This module consists of three parts: First,
the exception that is raised if a certain permission condition is not met.
Secondly, the assertion functions that test for certain permissions.  And
thirdly, top-level code that generates a ``has_permission_to_...`` function for
every ``assert_can_...`` function.

The idea is the following.  For example, there is a function called
``assert_can_view_sample``.  If the user can't view the sample, a
``PermissionError`` is raised.  Sometimes however, you just want to check it
without having to catch an exception.  Then, you use
``has_permission_to_view_sample``.  The parameters are the same but instead of
raising an exception, it returns ``True`` or ``False``.

The ``assert_can_...`` function are typically used at the beginning of views
where permissions need to be checked and every failure means an error.  By
contrast, the ``has_permission_to_...`` functions are used where a missing
permission just means that e.g. a link is not generated (for example, in the
``get_additional_template_context`` methods in the models).
"""

import hashlib
from django.utils.translation import ugettext as _, ugettext, ugettext_lazy
import django.contrib.auth.models
from django.conf import settings
# Attention! This is a cyclic import.  Don't use models in top-level code.
import chantal.samples.models
from chantal.samples.views import shared_utils

def translate_permission(permission_codename):
    u"""Translates a permission description to the user's language.

    :Parameters:
      - `permission_codename`: the codename of the permission, without the
        ``"samples."`` prefix

    :type permission_codename: str

    :Return:
      The name (aka short description) of the permission, translated to the
      current langauge.  It starts with a capital letter but doesn't end in a
      full stop.

    :rtype: unicode
    """
    return ugettext(django.contrib.auth.models.Permission.objects.get(codename=permission_codename))

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
    for permission in django.contrib.auth.models.Permission.objects.all().values("name", "codename"):
        if user.has_perm(permission["codename"]):
            has.append(ugettext(permission["name"]))
        else:
            has_not.append(ugettext(permission["name"]))
    return has, has_not

def get_user_hash(user):
    u"""Generates a secret hash that is connected with a user.  It is means as
    some sort of URL-based login for fetching feeds.  If the user accesses his
    feed via his aggregator, he is possibly not logged-in.  Because the
    aggregator cannot login by itself, the URL must be made unguessable.  This
    is done by appending the secret hash.

    Technically, it is the fist 10 characters of a salted SHA-1 hash of the
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
    return chantal.samples.models.SampleSeries.objects.filter(currently_responsible_person=user)

def get_allowed_physical_processes(user):
    allowed_physical_processes = []
    for physical_process_class in chantal.samples.models.all_physical_process_models:
        if has_permission_to_add_edit_physical_process(user, None, physical_process_class):
            allowed_physical_processes.append(physical_process_class)
    return allowed_physical_processes

class PermissionError(Exception):
    u"""Common class for all permission exceptions.

    :ivar description: the full description of the problem, possible remedy
      inclusive.  It should be a complete sentence, which addresses the user
      directly.  It should start with a capital letter and end with a full
      stop.  For example, it may be “You are not allowed to view sample 01B-410
      because you're not … Note that a head of an institute group may add you
      to new Chantal groups.”.

    :type description: unicode
    """
    def __init__(self, user, description, new_group_would_help=False):
        u"""Class constructor.

        :Parameters:
          - `user`: the user which has too few permissions
          - `description`: a sentence describing the denied action and what
            could be done about it
          - `new_group_would_help`: if ``True``, adding the user to a certain
            group would grant him the permission for the action

        :type user: ``django.contrib.auth.models.User``
        :type description: unicode
        :type new_group_would_help: bool
        """
        super(PermissionError, self).__init__(_(u"Permission denied: ") + description)
        self.user, self.description, self.new_group_would_help = user, description, new_group_would_help

def assert_can_view_sample(user, sample):
    u"""Tests whether the user can view the sample.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `sample`: the sample to be shown

    :type user: ``django.contrib.auth.models.User``
    :type sample: `models.Sample`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the
        sample.
    """
    if not user.has_perm("samples.view_all_samples") and sample.group not in user.groups.all() \
            and sample.currently_responsible_person != user:
        description = _(u"You are not allowed to view sample %s since you are not in the sample's group, nor are you "
                        u"its currently responsible person, nor are you a senior user.") % sample
        raise PermissionError(user, description, new_group_would_help=True)

def assert_can_add_edit_physical_process(user, process, process_class=None):
    u"""Tests whether the user can create or edit a physical process
    (i.e. deposition, measurement, etching process, clean room work etc).

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
    if not process_class:
        process_class = process.__class__
    elif process:
        assert process_class == process.__class__
    permission = translate_permission("add_edit_" + shared_utils.camel_case_to_underscores(process_class.__name__))
    if not user.has_perm(permission):
        if process:
            description = _(u"You are not allowed to edit the process “%(process)s” because you don't have the "
                            u"permission “%(permission)s”.") % {"process": unicode(process), "permission": permission}
        else:
            description = _(u"You are not allowed to add %(process_plural_name)s because you don't have the "
                            u"permission “%(permission)s”.") % \
                            {"process_plural_name": process_class._meta.verbose_name_plural, "permission": permission}
        raise PermissionError(user, description)

def assert_can_view_physical_process(user, process):
    u"""Tests whether the user can view a physical process (i.e. deposition,
    measurement, etching process, clean room work etc).

    :Parameters:
      - `user`: the user whose permission should be checked
      - `process`: The concrete process to view.

    :type user: ``django.contrib.auth.models.User``
    :type process: `models.Process`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the
        process.
    """
    permission = translate_permission("add_edit_" + shared_utils.camel_case_to_underscores(process.__class__.__name__))
    if not user.has_perm(permission):
        for sample in process.samples:
            if has_permission_to_view_sample(user, sample):
                break
        else:
            description = _(u"You are not allowed to view the process “%(process)s” because neither you have the "
                            u"permission “%(permission)s”, nor you are allowed to view one of the processed samples.") \
                            % {"process": unicode(process), "permission": permission}
            raise PermissionError(user, description, new_group_would_help=True)

def assert_can_edit_result_process(user, result_process):
    u"""Tests whether the user can edit a result process.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `result_process`: The result process to edit.

    :type user: ``django.contrib.auth.models.User``
    :type result_process: `models.Process`  FixMe: Should be ResultProcess

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit the result
        process.
    """
    if result_process.operator != user:
        description = _(u"You are not allowed to edit the result “%s” because you didn't create this result.") \
            % unicode(result_process)
        raise PermissionError(user, description)

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
    if sample_or_series.currently_responsible_person != user and sample_or_series.group not in user.groups.all():
        if isinstance(sample_or_series, chantal.samples.models.Sample):
            description = _(u"You are not allowed to add the result to %s because neither are you the currently "
                            u"responsible person for this sample, nor are you a member of its group.") % sample_or_series
        else:
            description = _(u"You are not allowed to add the result to %s because neither are you the currently "
                            u"responsible person for this sample series, nor are you a member of its group.") \
                            % sample_or_series
        raise PermissionError(user, description)

def assert_can_add_edit_substrate(user, substrate=None, affected_samples=None):
    u"""Tests whether the user can add or edit a substrate to *already
    existing* samples.  This is not used if samples and substrate process are
    created in the same request.

    :Parameters:
      - `user`: the user whose permission should be checked
      - `substrate`: the substrate process to be edited; ``None`` if the user
        wants to create one
      - `affected_samples`: the samples that belong to the newly created
        substrate process; ``None`` if the user wants to edit one

    :type user: ``django.contrib.auth.models.User``
    :type substrate: `models.Substrate`
    :type affected_samples: list of `models.Sample`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to add or edit the
        substrate process for those samples
    """
    assert (substrate and affected_names is None) or (substrate is None and affected_names is not None)
    if substrate:
        affected_names = substrate.samples
    for sample in affected_samples:
        if sample.currently_responsible_person != user:
            if substrate:
                description = _(u"You are not allowed to edit the substrate #%d because you are not allowed to edit "
                                u"all affected samples.") % substrate.pk
            else:
                description = _(u"You are not allowed to add a substrate because you are not allowed to edit all "
                                u"affected samples.")
            raise PermissionError(user, description, new_group_would_help=True)

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
    if sample.group and sample.currently_responsible_person != user:
        description = _(u"You are not allowed to edit the sample “%s” (including splitting and declaring dead) because "
                        u"you are not the currently responsible person for this sample.") % sample
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
    if sample_series.currently_responsible_person != user:
        description = _(u"You are not allowed to edit the sample series “%s” because "
                        u"you are not the currently responsible person for this sample series.") % sample_series
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
    if sample_series.currently_responsible_person != user and sample_series.group not in user.groups.all():
        description = _(u"You are not allowed to view the sample series “%s” because neither are"
                        u"you the currently responsible person for it, nor are you in its group.") % sample_series
        raise PermissionError(user, description)

def assert_can_add_external_operator(user):
    u"""Tests whether the user can add an external operator.

    :Parameters:
      - `user`: the user whose permission should be checked

    :type user: ``django.contrib.auth.models.User``

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to add an external
        operator.
    """
    if not user.has_perm("samples.add_external_operator"):
        description = _(u"You are not allowed to add an external operator because you don't have the permission “%s”.") \
            % translate_permission("add_external_operator")
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
    if external_operator.contact_person != user:
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
    if external_operator.contact_person != user and not user.has_perm("samples.view_all_samples"):
        description = _(u"You are not allowed to view this external operator because neither are you their "
                        u"current contact person, nor are you a senior user.")
        raise PermissionError(user, description)

def assert_can_edit_group_memberships(user):
    u"""Tests whether the user can change group memberships of other users, and
    add new groups.  This typically is a priviledge of heads of institute
    groups.

    :Parameters:
      - `user`: the user whose permission should be checked

    :type user: ``django.contrib.auth.models.User``

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit group
        memberships, nor to add new groups.
    """
    if not user.has_perm("samples.edit_group_memberships"):
        description = _(u"You are not allowed to change group memberships because you don't have the permission “%s”.") \
            % translate_permission("edit_group_memberships")
        raise PermissionError(user, description)

def assert_can_view_feed(hash_value, user):
    u"""Tests whether the requester that gave a certain ``hash_value`` can view
    the news feed of a certain ``user``.  Basically, this tests whether the
    requester *is* the user because only he can know the hash value.

    :Parameters:
      - `hash_value`: the hash value given by the requester
      - `user`: the user whose news feed is requested

    :type hash_value: str
    :type user: ``django.contrib.auth.models.User``

    :Exceptions:
      - `PermissionError`: raised if the requester is not allowed to view the
        user's news feed.
    """
    if hash_value != get_user_hash(user):
        description = _(u"You gave an invalid hash parameter in the query string.  "
                        u"Note that you can't access the news feed of another user.")
        raise PermissionError(None, description)


# Now, I inject the ``has_permission_to_...`` functions into this module for
# for every ``assert_can_...`` function found here.

def generate_permission_function(assert_func):
    def has_permission(*args, **keyw):
        try:
            assert_func(*args, **keyw)
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
