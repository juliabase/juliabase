#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Helper functions concerning sample names, and getting sample by name.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

from django.conf import settings
from samples import models


def sample_name_format(name, with_match_object=False):
    """Determines which sample name format the given name has.  It doesn't test
    whether the sample name is existing, nor if the initials are valid.

    :param name: the sample name

    :type name: unicode

    :return:
      The name of the sample name format and the respective match object.  The
      latter can be used to extract groups, for exampe.  ``None`` if the name
      had no valid format.

    :rtype: (unicode, re.MatchObject) or NoneType.
    """
    for name_format, properties in settings.SAMPLE_NAME_FORMATS.items():
        match = properties["regex"].match(name)
        if match:
            return (name_format, match) if with_match_object else name_format
    return (None, None) if with_match_object else None


renamable_name_formats = None
def get_renamable_name_formats():
    global renamable_name_formats
    if renamable_name_formats is None:
        renamable_name_formats = {name_format for (name_format, properties) in settings.SAMPLE_NAME_FORMATS.items()
                                  if properties.get("possible_renames")}
    return renamable_name_formats


def verbose_sample_name_format(name_format):
    """Returns the human-friendly, translatable name of the sample name format.  In
    English, it is in singular, and usable as an attribute to a noun.  In
    non-English language, you should choose something equivalent for the
    translation.

    :param name_format: The name format

    :type name_format: unicode

    :return:
      The verbose human-friendly name of this sample name format.

    :rtype: unicode
    """
    return settings.SAMPLE_NAME_FORMATS[name_format]["verbose_name"]


def get_sample(sample_name):
    """Lookup a sample by name.  You may also give an alias.  If more than one
    sample is found (can only happen via aliases), it returns a list.  Matching
    is exact.

    :param sample_name: the name or alias of the sample

    :type sample_name: unicode

    :return:
      the found sample.  If more than one sample was found, a list of them.  If
      none was found, ``None``.

    :rtype: `samples.models.Sample`, list of `samples.models.Sample`, or
      NoneType
    """
    try:
        sample = models.Sample.objects.get(name=sample_name)
    except models.Sample.DoesNotExist:
        aliases = [alias.sample for alias in models.SampleAlias.objects.filter(name=sample_name)]
        if len(aliases) == 1:
            return aliases[0]
        return aliases or None
    else:
        return sample


def does_sample_exist(sample_name):
    """Returns ``True`` if the sample name exists in the database.

    :param sample_name: the name or alias of the sample

    :type sample_name: unicode

    :return:
      whether a sample with this name exists

    :rtype: bool
    """
    return models.Sample.objects.filter(name=sample_name).exists() or \
        models.SampleAlias.objects.filter(name=sample_name).exists()


def normalize_sample_name(sample_name):
    """Returns the current name of the sample.

    :param sample_name: the name or alias of the sample

    :type sample_name: unicode

    :return:
      The current name of the sample.  This is only different from the input if
      you gave an alias.

    :rtype: unicode
    """
    if models.Sample.objects.filter(name=sample_name).exists():
        return sample_name
    try:
        sample_alias = models.SampleAlias.objects.get(name=sample_name)
    except models.SampleAlias.DoesNotExist:
        return
    else:
        return sample_alias.sample.name


def valid_new_sample_name(sample_name, new_sample_name):
    """Checks if the sample can be renamed in the new sample
    name. The new sample name must match any name pattern that are
    listet in the possible_renames properties.

    :param sample_name: The actual sample name
    :param new_sample_name: The new sample name

    :type sample_name: unicode
    :type new_sample_name: unicode

    :return:
      `True` if the sample can be renamed, `False` otherwise.

    :rtype: boolean
    """
    name_format = sample_name_format(sample_name)
    new_name_format = sample_name_format(new_sample_name)
    return new_name_format in settings.SAMPLE_NAME_FORMATS[name_format].get("possible_renames", set())
