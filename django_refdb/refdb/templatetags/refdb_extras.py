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


u"""Collection of tags and filters that I found useful for Django-RefDB.
"""

import re, codecs, os.path, unicodedata
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import escape
import django.utils.http
from django.contrib.markup.templatetags import markup
from django.utils.translation import ugettext as _
import chantal_common
# This *must* be absolute because otherwise, a Django module of the same name
# is imported.
from refdb.views import utils

register = template.Library()


@register.filter
def concise_title(value):
    u"""Filter to pick the abbreviated title of a publication or series with
    higher priority.  If it doesn't exist, it takes the full title.  This this
    doesn't exist too, it returns ``None``, so be aware to use the ``default``
    filter afterwards.
    """
    return utils.prettyprint_title_abbreviation(value.title_abbrev) if value.title_abbrev else value.title


@register.filter
def journal(value):
    u"""Filter to pick the abbreviated name of a journal with higher priority.
    If it doesn't exist, it takes the full name.  This this doesn't exist too,
    it returns ``None``, so be aware to use the ``default`` filter afterwards.

    In contrast to the `concise_title` filter, it assures that only a *journal*
    name is returned.  If the type of references doesn't have a journal name
    (e.g. it is a book), ``None`` is returned.
    """
    if value.type in ["ABST", "INPR", "JOUR", "JFULL", "MGZN", "NEWS"]:
        return utils.prettyprint_title_abbreviation(value.publication.title_abbrev) if value.publication.title_abbrev \
            else value.publication.title


class FlexibleFieldNode(template.Node):

    def __init__(self, nodelist, field_name):
        self.nodelist, self.field_name = nodelist, field_name

    def render(self, context):
        try:
            reference_type = template.Variable("reference.type").resolve(context)
        except template.VariableDoesNotExist:
            return ""
        labels = utils.labels[reference_type]
        if self.field_name in labels:
            return u"""<td class="label">%s:</td>%s""" % \
                (escape(labels[self.field_name]), self.nodelist.render(context))
        else:
            return u"""<td colspan="2"> </td>"""


@register.tag
def flexible_field(parser, token):
    try:
        tag_name, field_name = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%s tag requires exactly one argument" % token.contents.split()[0]
    if not (field_name[0] == field_name[-1] and field_name[0] in ('"', "'")):
        raise template.TemplateSyntaxError, "%s tag's argument should be in quotes" % tag_name
    nodelist = parser.parse(('end_flexible_field',))
    parser.delete_first_token()
    return FlexibleFieldNode(nodelist, field_name[1:-1])


@register.simple_tag
def markdown_field(field):
    if not field or field == u"—":
        return u"""<td colspan="0" class="value">—</td>"""
    else:
        return u"""<td colspan="0" class="bulk-text">%s</td>""" % chantal_common.templatetags.chantal.markdown(field)


class FullTextInfoNode(template.Node):

    def __init__(self, reference):
        self.reference = template.Variable(reference)
        self.words_to_highlight = template.Variable("words_to_highlight")

    @staticmethod
    def highlight(text, words_to_highlight):
        u"""Extracts the text part with the found hits and highlights them.
        More accurately, this routine searchs for the first occurence of one of
        the search terms in the full text of the respective PDF page and
        extracts the text around it (30 characters before, and 50 characters
        after it).  Then, it highlights all non-overlapping occurences of the
        search terms with ``<span>`` tags.

        These span tags can be of four classes: ``highlight-middle`` means that the
        search term is in the middle of a word, ``highlight-start`` at the
        start of a word, ``highlight-end`` at the end of the word, and
        ``highlight`` means that it is a complete word.  In the CSS, this can
        be used to use box padding smartly.

        :Parameters:
          - `text`: The complete text of the search hit.  Usually, it is what
            is returned by ``get_data()`` of a Xapian document.  Note that this
            *must* be Unicode, otherwise, you get an exception.
          - `words_to_highlight`: all words that should be highlighted in
            ``text``

        :type text: unicode
        :type words_to_highlight: set of unicode

        :Return:
          HTML code with the highlighted words

        :rtype: unicode
        """
        if not words_to_highlight:
            return None
        pattern = re.compile("|".join(re.escape(word) for word in words_to_highlight), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            start = max(match.start() - 30, 0)
            end = min(match.end() + 50, len(text))
        else:
            return None
        result = u"" if start == 0 else u"… "
        position = start
        while position < end:
            match = pattern.search(text, position)
            if match:
                if match.start() >= end:
                    result += escape(text[position:end])
                    break
                is_letter = lambda character: unicodedata.category(character)[0] == "L"
                letter_left = match.start() > 0 and is_letter(text[match.start() - 1])
                letter_right = match.end() < len(text) and is_letter(text[match.end()])
                if letter_left:
                    word_boundary = "-middle" if letter_right else "-end"
                else:
                    word_boundary = "-start" if letter_right else ""
                result += escape(text[position:match.start()]) + \
                    u"""<span class="highlight%s">""" % word_boundary + escape(match.group()) + u"</span>"
                position = match.end()
            else:
                result += escape(text[position:end])
                break
        if end != len(text):
            result += u" …"
        return result

    def render(self, context):
        try:
            reference = self.reference.resolve(context)
        except template.VariableDoesNotExist:
            return ""
        try:
            words_to_highlight = self.words_to_highlight.resolve(context)
        except template.VariableDoesNotExist:
            words_to_highlight = []
        if not hasattr(reference, "full_text_info"):
            return u""
        page_info = escape(_(u"Page %s") % reference.full_text_info.document.get_value(1))
        result = u"""<div class="full-text-info">""" + page_info
        highlighted_text = self.highlight(reference.full_text_info.document.get_data().decode("utf-8"), words_to_highlight)
        if highlighted_text:
            result += "<br/>" + highlighted_text
        result += u"</div>"
        return result


@register.tag
def full_text_info(parser, token):
    u"""Template tag for insertig full-text search info.  This means the found
    page, and the found string in its context on that page.

    The single argument is the reference which must have a ``full_text_info``
    attribute so that anything is displayed.  Additionally, this tag expects
    the variable ``words_to_highlight`` in the template context, which is a set
    of all words which are to be highlighted in the displayed context.
    """
    try:
        tag_name, reference = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%s tag requires exactly one argument" % token.contents.split()[0]
    return FullTextInfoNode(reference)
