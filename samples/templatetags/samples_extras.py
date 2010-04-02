#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collection of tags and filters that I found useful for Chantal.
"""

from __future__ import division
import string, re, sys
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import conditional_escape, escape
from django.utils.safestring import mark_safe
import django.utils.http
import django.core.urlresolvers
import samples.models, django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.markup.templatetags import markup
from django.conf import settings
import chantal_common.utils
import chantal_common.templatetags.chantal
import samples.views.utils

register = template.Library()

# FixMe: An audit must be made to see where variable content is not properly
# escaped.  Candidates are input_field and ValueFieldNode, but there are
# probably other, too.


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
        model, field = self.var.rsplit(".", 1)
        for app_name in settings.INSTALLED_APPS:
            try:
                model = sys.modules[app_name + ".models"].__dict__[model]
            except KeyError:
                continue
            break
        else:
            return u""
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
    user.  It is useful for creating labels.  The model name may be of any
    model in any installed app.  If two model names collide, the one of the
    firstly installed app is taken.
    """
    tag_name, var = token.split_contents()
    return VerboseNameNode(var)


@register.filter
def get_really_full_name(user, anchor_type="http", autoescape=False):
    u"""Unfortunately, Django's get_full_name method for users returns the
    empty string if the user has no first and surname set. However, it'd be
    sensible to use the login name as a fallback then. This is realised here.
    See also `samples.views.utils.get_really_full_name`.

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
        return chantal_common.templatetags.chantal.get_really_full_name(user, anchor_type, autoescape)
    elif isinstance(user, samples.models.ExternalOperator):
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
                         # Translation hint: Only change the <sup>h</sup>!
                     _(u"%Y-%m-%d %H<sup>h</sup>"),
                     u"%Y-%m-%d",
                         # Translation hint: Only change order and punctuation
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
    if isinstance(value, samples.models.Process):
        timestamp_ = value.timestamp
        inaccuracy = value.timestamp_inaccuracy
    else:
        timestamp_ = value["timestamp"]
        inaccuracy = value["timestamp_inaccuracy"]
    return mark_safe(chantal_common.utils.unicode_strftime(timestamp_, timestamp_formats[inaccuracy]))


sample_name_pattern = \
    re.compile(ur"(\W|\A)(?P<name>[0-9][0-9](([BVHLCS]-[0-9]{3,4}([-A-Za-z_/][-A-Za-z_/0-9]*)?)|"
               ur"(-([A-Z]{2}[0-9]{,2}|[A-Z]{3}[0-9]?|[A-Z]{4})-[-A-Za-z_/0-9]+)))(\W|\Z)", re.UNICODE)
sample_series_name_pattern = re.compile(ur"(\W|\A)(?P<name>[a-z_]+-[0-9][0-9]-[-A-Za-zÄÖÜäöüß_/0-9]+)(\W|\Z)", re.UNICODE)
@register.filter
@stringfilter
def markdown_samples(value):
    u"""Filter for formatting the value by assuming Markdown syntax.
    Additionally, sample names and sample series names are converted to
    clickable links.  Embedded HTML tags are always escaped.  Warning: You need
    at least Python Markdown 1.7 or later so that this works.

    FixMe: Before Markdown sees the text, all named entities are replaced, see
    `samples.views.utils.substitute_html_entities`.  This creates a mild
    escaping problem.  ``\&amp;`` becomes ``&amp;amp;`` instead of ``\&amp;``.
    It can only be solved by getting python-markdown to replace the entities,
    however, I can't easily do that without allowing HTML tags, too.
    """
    value = escape(chantal_common.utils.substitute_html_entities(unicode(value)))
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
                sample = samples.views.utils.get_sample(name)
                if isinstance(sample, samples.models.Sample):
                    database_item = sample
            else:
                try:
                    database_item = samples.models.SampleSeries.objects.get(name=name)
                except samples.models.SampleSeries.DoesNotExist:
                    pass
            name = name
            result += "[%s](%s)" % (name, database_item.get_absolute_url()) if database_item else name
        else:
            result += value[position:]
            break
    return markup.markdown(result)


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
            model = context[instance].__class__
            verbose_name = unicode(model._meta.get_field(field_name).verbose_name)
        verbose_name = verbose_name[0].upper() + verbose_name[1:]
        if self.unit == "yes/no":
            field = chantal_common.templatetags.chantal.fancy_bool(field)
            unit = None
        elif self.unit == "user":
            field = get_really_full_name(field)
            unit = None
        elif self.unit == "sccm_collapse":
            if not field:
                return u"""<td colspan="2"/>"""
            unit = "sccm"
        elif not field and field != 0:
            unit = None
            field = u"—"
        else:
            unit = self.unit
        return u"""<td class="label">%(label)s:</td><td class="value">%(value)s</td>""" % \
            {"label": verbose_name, "value": field if unit is None else quantity(field, unit)}


@register.tag
def value_field(parser, token):
    u"""Tag for inserting a field value into an HTML table.  It consists of two
    ``<td>`` elements, one for the label and one for the value, so it spans two
    columns.  This tag is primarily used in templates of show views, especially
    those used to compile the sample history.  Example::

        {% value_field layer.base_pressure "W" %}

    The unit (``"W"`` for “Watt”) is optional.  If you have a boolean field,
    you can give ``"yes/no"`` as the unit, which converts the boolean value to
    a yes/no string (in the current language).  For gas flow fields that should
    collapse if the gas wasn't used, use ``"sccm_collapse"``.
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