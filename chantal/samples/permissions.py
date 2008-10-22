#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Central permission checking.  This module consists of three parts: First,
the exceptions that are raised if a certain permission condition is not met.
Secondly, the assertion functions that test for certain permissions.  And
thirdly, top-level code that generates a ``has_permission_to_...`` function for
every ``assert_can_...`` function.

The idea is the following.  For example, there is a function called
``assert_can_view_sample``.  If the user can't view the sample, a
``PermissionViewSampleError`` is raised.  Sometimes however, you just want to
check it without having to catch an exception.  Then, you use
``has_permission_to_view_sample``.  The parameters are the same but instead of
raising an exception, it returns ``True`` or ``False``.

The ``assert_can_...`` function are typically used at the beginning of views
where permissions need to be checked and every failure means an error.  By
contrast, the ``has_permission_to_...`` functions are used where a missing
permission just means that e.g. a link is not generated (for example, in the
``get_additional_template_context`` methods in the models).
"""

from django.utils.translation import ugettext as _, ugettext, ugettext_lazy
import django.contrib.auth.models
# Attention! This is a cyclic import.  Don't use models in top-level code.
from chantal.samples import models
from chantal.samples.views import shared_utils

_ = ugettext_lazy
permission_translations = {"Can add an external operator": _("Can add an external operator"),
                           "Can create and edit 6-chamber depositions": _("Can create and edit 6-chamber depositions"),
                           "Can create and edit hall measurements": _("Can create and edit hall measurements"),
                           "Can create and edit large-area depositions": _("Can create and edit large-area depositions"),
                           "Can create and edit PDS measurements": _("Can create and edit PDS measurements"),
                           "Can view all samples (senior user)": _("Can view all samples (senior user)"),
                           "Can edit group memberships": _("Can edit group memberships"),
                           }
_ = ugettext

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
    return permission_translations[django.contrib.auth.models.Permission.objects.get(codename=permission_codename).name]

class PermissionError(Exception):
    u"""Common class for all permission exceptions.

    :ivar description: the full description of the problem, possible remedy
      inclusive.  It should be a complete sentence, which addresses the user
      directly.  It should start with a capital letter and end with a full
      stop.  For example, it may be “You are not allowed to view sample 01B-410
      because you're not … Note that a head of and institute group may add you
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
      - `user`: ``django.contrib.auth.models.User``
      - `sample`: `models.Sample`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to view the
        sample.
    """
    if not user.has_perm("samples.view_all_samples") and sample.group not in user.groups.all() \
            and sample.currently_responsible_person != user:
        description = _(u"You are not allowed to view sample %s since you are not in the sample's group, nor are you "
                        u"its currently responsible person, nor are you a senior user.") % sample
        raise PermissionError(user, description, new_group_would_help=True)


def assert_can_edit_sample(user, sample):
    u"""Tests whether the user can edit the sample.

    :Parameters:
      - `user`: ``django.contrib.auth.models.User``
      - `sample`: `models.Sample`

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to edit the
        sample.
    """
    if sample.currently_responsible_person != user:
        description = _(u"You are not allowed to edit sample %s since you are not the sample's currently "
                        u"responsible person.") % sample
        raise PermissionEditSampleError(user, description)


class PermissionAddEditPhysicalProcessError(PermissionError):
    def __init__(self, user, process_class, process, reason):
        if process:
            partial_description = _(u"edit the process “%s”") % unicode(process)
        else:
            partial_description = _(u"add %s") % process_class._meta.verbose_name_plural
        super(PermissionAddEditPhysicalProcessError, self).__init__(user, partial_description, reason)
        self.process_class, self.process = process_class, process

def assert_can_add_edit_physical_process(user, process_class, process):
    u"""Tests whether the user can create or edit a physical process
    (i.e. deposition, measurement, etching process, clean room work etc).

    :Parameters:
      - `user`: ``django.contrib.auth.models.User``
      - `process_class`: ``class`` (derived from `models.Process`)

    :Exceptions:
      - `PermissionError`: raised if the user is not allowed to create or edit
        the process.
    """
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
