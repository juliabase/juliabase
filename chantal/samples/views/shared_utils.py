#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions.  This is for low-level stuff.  Never import other
Chantal modules here, and avoid using Django, too.  The reason is that I'd like
to avoid cyclic imports, and I'd like to avoid being forced to ship the whole
of Django with the Remove Client (which uses this module).
"""

import re, string

def int_or_zero(number):
    u"""
    :Parameters:
      - `number`: a string that is supposed to contain an integer number

    :type number: str or unicode

    :Return:
      the ``int`` representation of ``number``, or 0 if it didn't represent a
      valid integer number

    :rtype: int
    """
    try:
        return int(number)
    except ValueError:
        return 0
    except TypeError:
        if number is None:
            return 0

def camel_case_to_underscores(name):
    u"""Converts a CamelCase identifier to one using underscores.  For example,
    ``"MySamples"`` is converted to ``"my_samples"``, and ``"PDSMeasurement"``
    to ``"pds_measurement"``.

    :Parameters:
      - `name`: the camel-cased identifier

    :type name: str

    :Return:
      the identifier in underscore notation

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i == 0:
            result.append(character.lower())
        elif character in string.ascii_uppercase and (i+1 < len(name) and name[i+1] not in string.ascii_uppercase):
            result.extend(("_", character.lower()))
        else:
            result.append(character.lower())
    return "".join(result)

def three_digits(number):
    u"""
    :Parameters:
      - `number`: the number of the deposition (only the number after the
        deposition system letter)

    :type number: int

    :Return:
      The number filled with leading zeros so that it has at least three
      digits.

    :rtype: unicode
    """
    return u"%03d" % number

quirky_sample_name_pattern = re.compile(ur"(?P<year>\d\d)(?P<letter>[BVHLCSbvhlcs])-?(?P<number>\d{1,4})"
                                        ur"(?P<suffix>[-A-Za-z_/][-A-Za-z_/0-9]*)?$")
def normalize_legacy_sample_name(sample_name):
    u"""Convert an old, probably not totally correct sample name to a valid
    sample name.  For example, a missing dash after the deposition letter is
    added, and the deposition letter is converted to uppercase.

    :Parameters:
      - `sample_name`: the original quirky name of the sample

    :type sample_name: unicode

    :Return:
      the corrected sample name

    :rtype: unicode

    :Exceptions:
      - `ValueError`: if the sample name was broken beyond repair.
    """
    match = quirky_sample_name_pattern.match(sample_name)
    if not match:
        raise ValueError("Sample name is too quirky to normalize")
    parts = match.groupdict(u"")
    parts["number"] = int(parts["number"])
    parts["letter"] = parts["letter"].upper()
    return u"%(year)s%(letter)s-%(number)03d%(suffix)s" % parts
