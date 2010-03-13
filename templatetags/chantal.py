#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""Collection of tags and filters that I found useful for Chantal.
"""

from __future__ import absolute_import

import re, codecs, os.path, unicodedata
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import escape
import django.utils.http
from django.contrib.markup.templatetags import markup
from django.utils.translation import ugettext as _
# This *must* be absolute because otherwise, a Django module of the same name
# is imported.
from chantal_common import utils

register = template.Library()


@register.filter
def get_really_full_name(user, anchor_type="http", autoescape=False):
    u"""Unfortunately, Django's get_full_name method for users returns the
    empty string if the user has no first and surname set. However, it'd be
    sensible to use the login name as a fallback then. This is realised here.
    See also `chantal_common.utils.get_really_full_name`.

    The optional parameter to this filter determines whether the name should be
    linked or not, and if so, how.  There are three possible parameter values:

    ``"http"`` (default)
        The user's name should be linked with his web page on Chantal

    ``"mailto"``
        The user's name should be linked with his email address

    ``"plain"``
        There should be no link, the name is just printed as plain unformatted
        text.

    """
    full_name = utils.get_really_full_name(user)
    if autoescape:
        full_name = conditional_escape(full_name)
    if anchor_type == "http":
        return mark_safe(u'<a href="%s">%s</a>' % (django.core.urlresolvers.reverse(
                    "samples.views.user_details.show_user", kwargs={"login_name": user.username}), full_name))
    elif anchor_type == "mailto":
        return mark_safe(u'<a href="mailto:%s">%s</a>' % (user.email, full_name))
    elif anchor_type == "plain":
        return mark_safe(full_name)
    else:
        return u""

get_really_full_name.needs_autoescape = True


@register.filter
@stringfilter
def markdown(value):
    u"""Filter for formatting the value by assuming Markdown syntax.  Embedded
    HTML tags are always escaped.  Warning: You need at least Python Markdown
    1.7 or later so that this works.

    FixMe: Before Markdown sees the text, all named entities are replaced, see
    `chantal_common.utils.substitute_html_entities`.  This creates a mild
    escaping problem.  ``\&amp;`` becomes ``&amp;amp;`` instead of ``\&amp;``.
    It can only be solved by getting python-markdown to replace the entities,
    however, I can't easily do that without allowing HTML tags, too.
    """
    return markup.markdown(escape(utils.substitute_html_entities(unicode(value))))


@register.simple_tag
def markdown_hint():
    u"""Tag for inserting a short remark that Markdown syntax must be used
    here, with a link to further information.
    """
    return u"""<span class="markdown-hint">(""" + _(u"""with %(markdown_link)s syntax""") \
        % {"markdown_link": u"""<a href="%s">Markdown</a>""" %
           django.core.urlresolvers.reverse("samples.views.markdown.sandbox")} + u")</span>"


@register.filter
def fancy_bool(boolean):
    u"""Filter for coverting a bool into a translated “Yes” or “No”.
    """
    _ = ugettext
    result = _(u"Yes") if boolean else _(u"No")
    return mark_safe(result)


@register.filter
@stringfilter
def urlquote(value):
    u"""Filter for quoting strings so that they can be used as parts of URLs.
    Note that also slashs »/« are escaped.

    Also note that this filter is “not safe” because for example ampersands
    need to be further escaped.
    """
    return django.utils.http.urlquote(value, safe="")
urlquote.is_safe = False


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


