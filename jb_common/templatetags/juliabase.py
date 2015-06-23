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


"""Collection of tags and filters that I found useful for JuliaBase.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six

import re
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape, escape
import django.utils.http
import markdown as markup
from django.utils.translation import ugettext as _, pgettext
from django.utils.text import capfirst
# This *must* be absolute because otherwise, a Django module of the same name
# is imported.
import jb_common.utils.base as utils

register = template.Library()


@register.filter(needs_autoescape=True)
def get_really_full_name(user, anchor_type="http", autoescape=False):
    """Unfortunately, Django's get_full_name method for users returns the
    empty string if the user has no first and surname set. However, it'd be
    sensible to use the login name as a fallback then. This is realised here.
    See also `jb_common.utils.get_really_full_name`.

    The optional parameter to this filter determines whether the name should be
    linked or not, and if so, how.  There are three possible parameter values:

    ``"http"`` (default)
        The user's name should be linked with his web page on JuliaBase

    ``"mailto"``
        The user's name should be linked with his email address

    ``"plain"``
        There should be no link, the name is just printed as plain unformatted
        text.

    """
    full_name = utils.get_really_full_name(user)
    if autoescape:
        full_name = conditional_escape(full_name)
    if anchor_type == "mailto" and not user.email:
        anchor_type = "plain"
    if anchor_type == "plain" or not user.jb_user_details.department:
        return mark_safe(full_name)
    elif anchor_type == "http":
        # FixMe: The view should be one of jb_common.
        return mark_safe('<a href="{0}">{1}</a>'.format(django.core.urlresolvers.reverse(
                    "jb_common.views.show_user", kwargs={"login_name": user.username}), full_name))
    elif anchor_type == "mailto":
        return mark_safe('<a href="mailto:{0}">{1}</a>'.format(user.email, full_name))
    else:
        return ""


math_delimiter_pattern = re.compile(r"(?<!\\)\$", re.UNICODE)

def substitute_formulae(string):
    """Substitute all math equations between ``$…$`` by the formula graphics.
    This is achieved by using Google's formula chart API.  This means that I
    simply insert an ``<img>`` tag with a Google URL for every formula.

    Note that any HTML-like material which is found along the way is escaped.
    Thus, this routine returns a safe string.

    :param string: raw text from the user or the database

    :type string: unicode

    :return:
      The escaped string, marked as safe and ready to be used in the output
      HTML.  Any LaTeX formulae are replaced by Google images.

    :rtype: safe unicode
    """
    if "$" not in string:
        return mark_safe(escape(string))
    no_further_match = False
    position = 0
    result = ""
    while position < len(string):
        match = math_delimiter_pattern.search(string, position)
        if match:
            start = match.start() + 1
            match = math_delimiter_pattern.search(string, start + 1)
            if match:
                end = match.start()
                latex_markup = string[start:end]
                result += escape(string[position:start - 1]) + \
                    """<img style="vertical-align: middle" alt="{0}" """ \
                    """src="https://chart.googleapis.com/chart?chf=bg,s,00000000&cht=tx&chl={1}"/>""".\
                    format(escape(" ".join(latex_markup.split())).replace("\\", "&#x5c;"),
                           urlquote_plus(r"\Large " + latex_markup))
                position = end + 1
            else:
                no_further_match = True
        else:
            no_further_match = True
        if no_further_match:
            result += escape(string[position:])
            break
    return mark_safe(result)


@register.filter
@stringfilter
def markdown(value, margins="default"):
    """Filter for formatting the value by assuming Markdown syntax.  Embedded
    HTML tags are always escaped.  Warning: You need at least Python Markdown
    1.7 or later so that this works.

    FixMe: Before Markdown sees the text, all named entities are replaced, see
    :py:func:`jb_common.utils.substitute_html_entities`.  This creates a mild
    escaping problem.  ``\&amp;`` becomes ``&amp;amp;`` instead of ``\&amp;``.
    It can only be solved by getting python-markdown to replace the entities,
    however, I can't easily do that without allowing HTML tags, too.
    """
    result = markup.markdown(substitute_formulae(utils.substitute_html_entities(six.text_type(value))))
    if result.startswith("<p>"):
        if margins == "collapse":
            result = mark_safe("""<p style="margin: 0pt">""" + result[3:])
    return mark_safe(result)


@register.simple_tag
def markdown_hint():
    """Tag for inserting a short remark that Markdown syntax must be used
    here, with a link to further information.
    """
    return """<span class="markdown-hint">(""" + _("""with {markdown_link} syntax""") \
        .format(markdown_link="""<a href="{0}">Markdown</a>""".format(
           django.core.urlresolvers.reverse("jb_common.views.markdown_sandbox"))) + ")</span>"


@register.filter
def fancy_bool(boolean):
    """Filter for coverting a bool into a translated “Yes” or “No”.
    """
    result = capfirst(_("yes")) if boolean else capfirst(_("no"))
    return mark_safe(result)


@register.filter
def contenttype_name(contenttype):
    """Filter for getting the verbose name of the contenttype's model class.
    FixMe: This is superfluous if #16803 is resolved.  Then, you can simply use
    a field of the contettype instance.
    """
    return mark_safe(contenttype.model_class()._meta.verbose_name)


@register.filter
@stringfilter
def urlquote(value):
    """Filter for quoting strings so that they can be used as parts of URLs.
    Note that also slashs »/« are escaped.

    Also note that this filter is “not safe” because for example ampersands
    need to be further escaped.
    """
    return django.utils.http.urlquote(value, safe="")
urlquote.is_safe = False


@register.filter
@stringfilter
def urlquote_plus(value):
    """Filter for quoting URLs so that they can be used within other URLs.
    This is useful for added “next” URLs in query strings, for example::

        <a href="{{ process.edit_url }}?next={{ sample.get_absolute_url|urlquote_plus }}"
               >{% trans 'edit' %}</a>
    """
    return django.utils.http.urlquote_plus(value, safe="/")
urlquote_plus.is_safe = False


@register.simple_tag
def input_field(field):
    """Tag for inserting a field value into an HTML table as an editable
    field.  It consists of two ``<td>`` elements, one for the label and one for
    the value, so it spans two columns.  This tag is primarily used in
    templates of edit views.  Example::

        {% input_field deposition.number %}
    """
    result = """<td class="field-label"><label for="id_{html_name}">{label}:</label></td>""".format(
        html_name=field.html_name, label=field.label)
    help_text = """<span class="help">({0})</span>""".format(field.help_text) if field.help_text else ""
    try:
        unit = field.field.unit
    except AttributeError:
        unit = ""
    else:
        unit = """<span class="unit-of-measurement">{unit}</span>""".format(unit=unit)
    result += """<td class="field-input">{field}{unit}{help_text}</td>""".format(field=field, unit=unit, help_text=help_text)
    return result


@register.inclusion_tag("error_list.html")
def error_list(form, form_error_title, outest_tag="<table>", colspan=1):
    """Includes a comprehensive error list for one particular form into the
    page.  It is an HTML table, so take care that the tags are nested
    properly.  Its template can be found in the file ``"error_list.html"``.

    :param form: the bound form whose errors should be displayed; if ``None``,
        nothing is generated
    :param form_error_title: The title used for general error messages.  These
        are not connected to one particular field but the form as a
        whole. Typically, they are generated in the ``is_referentially_valid``
        functions.
    :param outest_tag: May be ``"<table>"`` or ``"<tr>"``, with ``"<table>"`` as
        the default.  It is the outmost HTML tag which is generated for the
        error list.
    :param colspan: the width of the table in the number of columns; necessary
        because those &%$# guys of WHATWG have dropped colspan="0"; see
        http://www.w3.org/Bugs/Public/show_bug.cgi?id=13770

    :type form: forms.Form
    :type form_error_title: unicode
    :type outest_tag: unicode
    :type colspan: int
    """
    if outest_tag == "<table>":
        assert colspan == 1
    return {"form": form, "form_error_title": form_error_title, "colspan": colspan, "outest_tag": outest_tag}


@register.simple_tag
def ptrans(context, string):
    # FixMe: I hope that in upcoming Django versions, this will be included
    # anyway.  Then, this tag should be deleted.
    """Tag for translating a string with context.  Example::

        {% ptrans 'month' 'May' %}
    """
    return pgettext(context, string)


@register.filter
def times08(value):
    return value * 0.8
