#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collection of tags and filters that I found useful for Django-RefDB.
"""

import re, codecs, os.path, unicodedata
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import escape
import django.utils.http
from django.contrib.markup.templatetags import markup
from django.utils.translation import ugettext as _
# This *must* be absolute because otherwise, a Django module of the same name
# is imported.
from refdb.views import utils

register = template.Library()


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
        return u"""<td colspan="0" class="bulk-text">%s</td>""" % markdown(field)


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
