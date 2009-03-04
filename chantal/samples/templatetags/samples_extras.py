#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collection of tags and filters that I found useful for Chantal.
"""

from __future__ import division
import string, re
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
import django.utils.http
import django.core.urlresolvers
import chantal.samples.models, django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.markup.templatetags import markup
import chantal.samples.views.utils

register = template.Library()


@register.filter
def quantity(value, unit=None, autoescape=False):
    u"""Filter for pretty-printing a physical quantity.  It converts 3.4e-3
    into 3.4·10⁻³.  The number is the part that is actually filtered, while the
    unit is the optional argument of this filter.  So, you may write::

        {{ deposition.pressure|quantity:"mbar" }}

    """
    if value is None:
        return None
    value_string = u"%g" % value if isinstance(value, float) else unicode(value)
    if autoescape:
        value_string = conditional_escape(value_string)
        unit = conditional_escape(unit) if unit else None
    result = u""
    i = 0
    match = re.match(ur"(?P<leading>.*?)(?P<prepoint>[-+]?\d*)(\.(?P<postpoint>\d+))?"
                     ur"(e(?P<exponent>[-+]?\d+))?(?P<trailing>.*)", value_string)
    match_dict = match.groupdict(u"")
    result = match_dict["leading"] + match_dict["prepoint"].replace(u"-", u"−")
    if match_dict["postpoint"]:
        result += "." + match_dict["postpoint"]
    if match_dict["exponent"]:
        result += u" · 10<sup>"
        match_exponent = re.match(ur"(?P<sign>[-+])?0*(?P<digits>\d+)", match_dict["exponent"])
        if match_exponent.group("sign") == "-":
            result += u"−"
        result += match_exponent.group("digits")
        result += u"</sup>"
    result += match_dict["trailing"]
    if unit:
        result += "&nbsp;" + unit
    return mark_safe(result)
quantity.needs_autoescape = True


@register.filter
def fancy_bool(boolean):
    u"""Filter for coverting a bool into a translated “Yes” or “No”.
    """
    _ = ugettext
    result = _(u"Yes") if boolean else _(u"No")
    return mark_safe(result)


@register.filter
def three_digits(number):
    u"""Filter for padding an integer with zeros so that it has at least three
    digits.
    """
    return mark_safe(u"%03d" % number)


class VerboseNameNode(template.Node):
    u"""Helper class for the tag `verbose_name`.  While `verbose_name` does the
    parsing, this class does the actual processing.
    """

    def __init__(self, var):
        self.var = var

    def render(self, context):
        if "." not in self.var:
            verbose_name = unicode(context[self.var]._meta.verbose_name)
        else:
            model, field = self.var.rsplit(".", 1)
            if model == "django.contrib.auth.models.User":
                model = django.contrib.auth.models.User
            else:
                model = chantal.samples.models.__dict__[model]
            verbose_name = unicode(model._meta.get_field(field).verbose_name)
        if verbose_name:
            verbose_name = verbose_name[0].upper() + verbose_name[1:]
        return verbose_name


@register.tag
def verbose_name(parser, token):
    u"""Tag for retrieving the descriptive name for an instance attribute.  For
    example::

        {% verbose_name Deposition.pressure %}

    will print “pressure”.  Note that it will be translated for a non-English
    user.  It is useful for creating labels.

    Currently, this tag supports all Chantal models as well as
    ``django.contrib.auth.models.User``.  Other models could be added
    manually.
    """
    tag_name, var = token.split_contents()
    return VerboseNameNode(var)


@register.simple_tag
def markdown_hint():
    u"""Tag for inserting a short remark that Markdown syntax must be used
    here, with a link to further information.
    """
    return u"""<span class="markdown-hint">(""" + _(u"""with %(markdown_link)s syntax""") \
        % {"markdown_link": u"""<a href="%s">Markdown</a>""" %
           django.core.urlresolvers.reverse("samples.views.markdown.sandbox")} + u")</span>"


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


@register.filter
def get_really_full_name(user, anchor_type="http", autoescape=False):
    u"""Unfortunately, Django's get_full_name method for users returns the
    empty string if the user has no first and surname set. However, it'd be
    sensible to use the login name as a fallback then. This is realised here.
    See also `chantal.samples.views.utils.get_really_full_name`.

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
    if isinstance(user, django.contrib.auth.models.User):
        full_name = chantal.samples.views.utils.get_really_full_name(user)
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
    elif isinstance(user, chantal.samples.models.ExternalOperator):
        full_name = user.name
        if autoescape:
            full_name = conditional_escape(full_name)
        if anchor_type == "http":
            return mark_safe(u'<a href="%s">%s</a>' % (django.core.urlresolvers.reverse(
                        "samples.views.external_operator.show", kwargs={"external_operator_id": user.pk}), full_name))
        elif anchor_type == "mailto":
            return mark_safe(u'<a href="mailto:%s">%s</a>' % (user.email, full_name))
        elif anchor_type == "plain":
            return mark_safe(full_name)
        else:
            return u""
    return u""

get_really_full_name.needs_autoescape = True


@register.filter
def calculate_silane_concentration(value):
    u"""Filter for calculating the silane concentration for a large-area
    deposition layer from the silane and hydrogen fluxes.
    """
    silane = float(value.sih4)*0.6
    hydrogen = float(value.h2)
    if silane + hydrogen == 0:
        return None
    # Cheap way to cut the digits
    return float(u"%5.2f" % (100 * silane / (silane + hydrogen)))


timestamp_formats = (u"%Y-%m-%d %H:%M:%S",
                     u"%Y-%m-%d %H:%M",
                     _(u"%Y-%m-%d %H<sup>h</sup>"),
                     u"%Y-%m-%d",
                     _(u"%b %Y"),
                     u"%Y",
                     _(u"date unknown"))
@register.filter
def timestamp(value):
    u"""Filter for formatting the timestamp of a process properly to reflect
    the inaccuracy connected with this timestamp.

    :Parameters:
      - `value`: the process whose timestamp should be formatted

    :type value: `models.Process` or dict mapping str to object

    :Return:
      the rendered timestamp

    :rtype: unicode
    """
    if isinstance(value, chantal.samples.models.Process):
        timestamp_ = value.timestamp
        inaccuracy = value.timestamp_inaccuracy
    else:
        timestamp_ = value["timestamp"]
        inaccuracy = value["timestamp_inaccuracy"]
    return mark_safe(utils.unicode_strftime(timestamp_, timestamp_formats[inaccuracy]))


sample_name_pattern = \
    re.compile(ur"(\W|\A)(?P<name>[0-9][0-9](([BVHLCS]-[0-9]{3,4}([-A-Za-z_/][-A-Za-z_/0-9]*)?)|"
               ur"(-([A-Z]{2}[0-9]{,2}|[A-Z]{3}[0-9]?|[A-Z]{4})-[-A-Za-z_/0-9]+)))(\W|\Z)", re.UNICODE)
sample_series_name_pattern = re.compile(ur"(\W|\A)(?P<name>[a-z_]+-[0-9][0-9]-[-A-Za-zÄÖÜäöüß_/0-9]+)(\W|\Z)", re.UNICODE)
@register.filter
@stringfilter
def markdown(value):
    u"""Filter for formatting the value by assuming Markdown syntax.
    Additionally, sample names and sample series names are converted to
    clickable links.  Embedded HTML tags are always escaped.  Warning: You need
    at least Python Markdown 1.7 or later so that this works.

    FixMe: Before Markdown sees the text, all named entities are replaced, see
    `chantal.samples.views.utils.substitute_html_entities`.  This creates a
    mild escaping problem.  ``\&amp;`` becomes ``&amp;amp;`` instead of
    ``\&amp;``.  It can only be solved by getting python-markdown to replace
    the entities, however, I can't easily do that without allowing HTML tags,
    too.
    """
    value = escape(chantal.samples.views.utils.substitute_html_entities(unicode(value)))
    position = 0
    result = u""
    while position < len(value):
        sample_match = sample_name_pattern.search(value, position)
        sample_series_match = sample_series_name_pattern.search(value, position)
        sample_start = sample_match.start("name") if sample_match else len(value)
        sample_series_start = sample_series_match.start("name") if sample_series_match else len(value)
        next_is_sample = sample_start <= sample_series_start
        match = sample_match if next_is_sample else sample_series_match
        if match:
            start, end = match.span("name")
            result += value[position:start]
            position = end
            name = match.group("name")
            database_item = None
            if next_is_sample:
                sample = chantal.samples.views.utils.get_sample(name)
                if isinstance(sample, chantal.samples.models.Sample):
                    database_item = sample
            else:
                try:
                    database_item = chantal.samples.models.SampleSeries.objects.get(name=name)
                except chantal.samples.models.SampleSeries.DoesNotExist:
                    pass
            name = name
            result += "[%s](%s)" % (name, database_item.get_absolute_url()) if database_item else name
        else:
            result += value[position:]
            break
    return markup.markdown(result)


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


class ValueFieldNode(template.Node):
    u"""Helper class to realise the `value_field` tag.
    """

    def __init__(self, field, unit):
        self.field_name = field
        self.field = template.Variable(field)
        self.unit = unit

    def render(self, context):
        field = self.field.resolve(context)
        if "." not in self.field_name:
            verbose_name = unicode(context[self.field_name]._meta.verbose_name)
        else:
            instance, field_name = self.field_name.rsplit(".", 1)
            model = context[instance].__class__.__name__
            if model == "User":
                model = django.contrib.auth.models.User
            else:
                model = chantal.samples.models.__dict__[model]
            verbose_name = unicode(model._meta.get_field(field_name).verbose_name)
        verbose_name = verbose_name[0].upper() + verbose_name[1:]
        if self.unit == "yes/no":
            field = fancy_bool(field)
            self.unit = None
        elif self.unit == "user":
            field = get_really_full_name(field)
            self.unit = None
        elif not field and field != 0:
            self.unit = None
            field = u"—"
        return u"""<td class="label">%(label)s:</td><td class="value">%(value)s</td>""" % \
            {"label": verbose_name, "value": field if self.unit is None else quantity(field, self.unit)}


@register.tag
def value_field(parser, token):
    u"""Tag for inserting a field value into an HTML table.  It consists of two
    ``<td>`` elements, one for the label and one for the value, so it spans two
    columns.  This tag is primarily used in tamplates of show views, especially
    those used to compile the sample history.  Example::

        {% value_field layer.base_pressure "W" %}

    The unit (``"W"`` for “Watt”) is optional.  If you have a boolean field,
    you can give ``"yes/no"`` as the unit, which converts the boolean value to
    a yes/no string (in the current language).
    """
    tokens = token.split_contents()
    if len(tokens) == 3:
        tag, field, unit = tokens
        if not (unit[0] == unit[-1] and unit[0] in ('"', "'")):
            raise template.TemplateSyntaxError, "value_field's unit argument should be in quotes"
        unit = unit[1:-1]
    elif len(tokens) == 2:
        tag, field = tokens
        unit = None
    else:
        raise template.TemplateSyntaxError, "value_field requires one or two arguments"
    return ValueFieldNode(field, unit)
