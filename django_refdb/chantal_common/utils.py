#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Chantal.  Chantal is published under the MIT license.  A
# copy of this licence is shipped with Chantal in the file LICENSE.


from __future__ import absolute_import

import codecs, re, os.path
from functools import update_wrapper
import django.http
from django.forms.util import ErrorList, ValidationError


class HttpResponseUnauthorized(django.http.HttpResponse):
    u"""The response sent back in case of a permission error.  This is another
    missing response class in Django.  I have no clue why they leave out such
    trivial code.
    """
    status_code = 401


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


def append_error(form, error_message, fieldname="__all__"):
    u"""This function is called if a validation error is found in form data
    which cannot be found by the ``is_valid`` method itself.  The reason is
    very simple: For many types of invalid data, you must take other forms in
    the same view into account.

    See, for example, `split_after_deposition.is_referentially_valid`.

    :Parameters:
      - `form`: the form to which the erroneous field belongs
      - `error_message`: the message to be presented to the user
      - `fieldname`: the name of the field that triggered the validation
        error.  It is optional, and if not given, the error is considered an
        error of the form as a whole.

    :type form: ``forms.Form`` or ``forms.ModelForm``.
    :type fieldname: str
    :type error_message: unicode
    """
    # FixMe: Is it really a good idea to call ``is_valid`` here?
    # ``append_error`` is also called in ``clean`` methods after all.
    form.is_valid()
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)


dangerous_markup_pattern = re.compile(r"([^\\]|\A)!\[|[\n\r][-=]")
def check_markdown(text):
    u"""Checks whether the Markdown input by the user contains only permitted
    syntax elements.  I forbid images and headings so far.

    :Parameters:
      - `text`: the Markdown input to be checked

    :Exceptions:
      - `ValidationError`: if the ``text`` contained forbidden syntax
        elements.
    """
    if dangerous_markup_pattern.search(text):
        raise ValidationError(_(u"You mustn't use image and headings syntax in Markdown markup."))


class _AddHelpLink(object):
    u"""Internal helper class in order to realise the `help_link` function
    decorator.
    """

    def __init__(self, original_view_function, help_link):
        self.original_view_function = original_view_function
        self.help_link = help_link
        update_wrapper(self, original_view_function)

    def __call__(self, request, *args, **kwargs):
        request.chantal_help_link = self.help_link
        return self.original_view_function(request, *args, **kwargs)


def help_link(link):
    u"""Function decorator for views functions to set a help link for the view.
    The help link is embedded into the top line in the layout, see the template
    ``base.html``.  Currently, it is prepended with ``"/trac/chantal/wiki/"``.

    :Parameters:
      - `link`: the relative URL to the help page.

    :type link: str
    """

    def decorate(original_view_function):
        return _AddHelpLink(original_view_function, link)

    return decorate


