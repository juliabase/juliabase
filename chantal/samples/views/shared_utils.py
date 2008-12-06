#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""General helper functions.  This is for low-level stuff.  Never import other
Chantal modules here, and avoid using Django, too.  The reason is that I'd like
to avoid cyclic imports, and I'd like to avoid being forced to ship the whole
of Django with the Remove Client (which uses this module).

Note that all names defined here are also available in `utils`, so this module
ist really only interesting for the Remote Client.
"""

import re, string, codecs, os.path

def get_really_full_name(user):
    u"""Unfortunately, Django's ``get_full_name`` method for users returns the
    empty string if the user has no first and surname set.  However, it'd be
    sensible to use the login name as a fallback then.  This is realised here.

    :Parameters:
      - `user`: the user instance
    :type user: ``django.contrib.auth.models.User``

    :Return:
      The full, human-friendly name of the user

    :rtype: unicode
    """
    return user.get_full_name() or unicode(user)

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

entities = {}
for line in codecs.open(os.path.join(os.path.dirname(__file__), "entities.txt"), encoding="utf-8"):
    entities[line[:12].rstrip()] = line[12]
entity_pattern = re.compile(r"&[A-Za-z0-9]{2,8};")
def substitute_html_entities(text):
    u"""Searches for all ``&entity;`` named entities in the input and replaces
    them by their unicode counterparts.  For example, ``&alpha;``
    becomes ``α``.  Escaping is not possible unless you spoil the pattern with
    a character that is later removed.  But this routine doesn't have an
    escaping mechanism.

    :Parameters:
      - `text`: the user's input to be processed

    :type text: unicode

    :Return:
      ``text`` with all named entities replaced by single unicode characters

    :rtype: unicode
    """
    result = u""
    position = 0
    while position < len(text):
        match = entity_pattern.search(text, position)
        if match:
            start, end = match.span()
            character = entities.get(text[start+1:end-1])
            result += text[position:start] + character if character else text[position:end]
            position = end
        else:
            result += text[position:]
            break
    return result

