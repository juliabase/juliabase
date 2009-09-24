#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collection of tags and filters that I found useful for Django-RefDB.
"""

import re, codecs, os.path
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import escape
import django.utils.http
from django.contrib.markup.templatetags import markup
# This *must* be absolute because otherwise, a Django module of the same name
# is imported.
from refdb.views import utils  

register = template.Library()


@register.filter
def display_reference_type(value):
    u"""Filter for converting a short-form reference type into its verbose
    form, e.g. ``"JOUR"`` becomes ``"journal paper"``.
    """
    return utils.reference_types[value]


# FixMe: This is a duplicate of Chantal

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


# FixMe: This is a duplicate of Chantal

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


# FixMe: This is a duplicate of Chantal

@register.filter
@stringfilter
def urlquote_plus(value):
    u"""Filter for quoting URLs so that they can be used within other URLs.
    This is useful for added “next” URLs in query strings, for example::

        <a href="{{ process.edit_url }}?next={{ sample.get_absolute_url|urlquote_plus }}"
               >{% trans 'edit' %}</a>
    """
    return django.utils.http.urlquote_plus(value, safe="/")
urlquote_plus.is_safe = False


# FixMe: This is a duplicate of Chantal

@register.simple_tag
def input_field(field):
    u"""Tag for inserting a field value into an HTML table as an editable
    field.  It consists of two ``<td>`` elements, one for the label and one for
    the value, so it spans two columns.  This tag is primarily used in
    tamplates of edit views.  Example::

        {% input_field deposition.number %}
    """
    result = u"""<td class="label"><label for="id_%(html_name)s">%(label)s:</label></td>""" % \
        {"html_name": field.html_name, "label": field.label}
    help_text = u""" <span class="help">(%s)</span>""" % field.help_text if field.help_text else u""
    result += u"""<td class="input">%(field)s%(help_text)s</td>""" % {"field": field, "help_text": help_text}
    return result


# FixMe: This is a duplicate of Chantal

@register.inclusion_tag("error_list.html")
def error_list(form, form_error_title, outest_tag=u"<table>"):
    u"""Includes a comprehensive error list for one particular form into the
    page.  It is an HTML table, so take care that the tags are nested
    properly.  Its template can be found in the file ``"error_list.html"``.

    :Parameters:
      - `form`: the bound form whose errors should be displayed; if ``None``,
        nothing is generated
      - `form_error_title`: The title used for general error messages.  These
        are not connected to one particular field but the form as a
        whole. Typically, they are generated in the ``is_referentially_valid``
        functions.
      - `outest_tag`: May be ``"<table>"`` or ``"<tr>"``, with ``"<table>"`` as
        the default.  It is the outmost HTML tag which is generated for the
        error list.

    :type form: ``forms.Form``
    :type form_error_title: unicode
    :type outest_tag: unicode
    """
    return {"form": form, "form_error_title": form_error_title, "outest_tag": outest_tag}
