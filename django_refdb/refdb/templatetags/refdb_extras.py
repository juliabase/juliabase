#!/usr/bin/env python
# -*- coding: utf-8 -*-

# FixMe: Probably too man imports
import string, re, codecs, os.path
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
import django.utils.http
import django.core.urlresolvers
import refdb.models, django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.markup.templatetags import markup
from refdb import utils

register = template.Library()


@register.filter
def display_reference_type(value):
    return utils.reference_types[value]


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


@register.filter
@stringfilter
def markdown(value):
    u"""Filter for formatting the value by assuming Markdown syntax.  Embedded
    HTML tags are always escaped.  Warning: You need at least Python Markdown
    1.7 or later so that this works.

    FixMe: Before Markdown sees the text, all named entities are replaced, see
    `samples.views.utils.substitute_html_entities`.  This creates a mild
    escaping problem.  ``\&amp;`` becomes ``&amp;amp;`` instead of ``\&amp;``.
    It can only be solved by getting python-markdown to replace the entities,
    however, I can't easily do that without allowing HTML tags, too.
    """
    return markup.markdown(escape(substitute_html_entities(unicode(value))))
