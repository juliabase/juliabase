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

    It is also possible to give a list of two values.  This is formatted in a
    from–to notation.
    """
    def pretty_print_number(number):
        u"""Pretty-print a single value.  For the from–to notation, this
        function is called twice.
        """
        value_string = u"{0:g}".format(number) if isinstance(number, float) else unicode(number)
        if autoescape:
            value_string = conditional_escape(value_string)
        result = u""
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
        return result

    if value is None:
        return None
    if isinstance(value, (tuple, list)):
        result = u"{0}–{1}".format(pretty_print_number(value[0]), pretty_print_number(value[1]))
    else:
        result = pretty_print_number(value)
    if autoescape:
        unit = conditional_escape(unit) if unit else None
    if unit:
        result += "&nbsp;" + unit
    return mark_safe(result)
quantity.needs_autoescape = True


@register.filter
def three_digits(number):
    u"""Filter for padding an integer with zeros so that it has at least three
    digits.
    """
    return mark_safe(u"{0:03}".format(number))


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
            verbose_name = samples.views.utils.capitalize_first_letter(verbose_name)
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
            return mark_safe(u'<a href="{0}">{1}</a>'.format(django.core.urlresolvers.reverse(
                        "samples.views.external_operator.show", kwargs={"external_operator_id": user.pk}), full_name))
        elif anchor_type == "mailto":
            return mark_safe(u'<a href="mailto:{0}">{1}</a>'.format(user.email, full_name))
        elif anchor_type == "plain":
            return mark_safe(full_name)
        else:
            return u""
    return u""

get_really_full_name.needs_autoescape = True


@register.filter
def get_safe_operator_name(user, autoescape=False):
    u"""Return the name of the operator (with the markup generated by
    `get_really_full_name` and the ``"http"`` option) unless it is a
    confidential external operator.
    """
    if isinstance(user, django.contrib.auth.models.User) or \
            (isinstance(user, samples.models.ExternalOperator) and not user.confidential):
        return get_really_full_name(user, "http", autoescape)
    name = _(u"Confidential operator #{number}").format(number=user.pk)
    if autoescape:
        name = conditional_escape(name)
    return mark_safe(u'<a href="{0}">{1}</a>'.format(django.core.urlresolvers.reverse(
                "samples.views.user_details.show_user", kwargs={"login_name": user.contact_person.username}), name))

get_safe_operator_name.needs_autoescape = True


@register.filter
def calculate_silane_concentration(value):
    u"""Filter for calculating the silane concentration for a large-area
    deposition layer from the silane and hydrogen fluxes.
    """
    silane = float(value.sih4) * 0.6
    hydrogen = float(value.h2)
    if silane + hydrogen == 0:
        return None
    calculate_sc = lambda s: 100 * s / (s + hydrogen)
    sc = calculate_sc(silane)
    if not value.sih4_end:
        # Cheap way to cut the digits
        return float(u"{0:5.2f}".format(sc))
    else:
        silane_max = float(value.sih4_end) * 0.6
        sc_max = calculate_sc(silane_max)
        return float(u"{0:5.2f}".format(sc)), float(u"{0:5.2f}".format(sc_max))


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


# FixMe: This pattern should probably be moved to settings.py.
sample_name_pattern = \
    re.compile(ur"""(\W|\A)(?P<name>[0-9][0-9][A-Z]-[0-9]{3,4}([-A-Za-z_/][-A-Za-z_/0-9#]*)?|  # old-style sample name
                            ([0-9][0-9]-([A-Z]{2}[0-9]{,2}|[A-Z]{3}[0-9]?|[A-Z]{4})|           # initials of a user
                            [A-Z]{2}[0-9][0-9]|[A-Z]{3}[0-9]|[A-Z]{4})                         # initials of an external
                            -[-A-Za-z_/0-9#]+)(\W|\Z)""", re.UNICODE | re.VERBOSE)
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
    value = chantal_common.templatetags.chantal.substitute_formulae(
        chantal_common.utils.substitute_html_entities(unicode(value)))
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
            result += "[{0}]({1})".format(name, database_item.get_absolute_url()) if database_item else name
        else:
            result += value[position:]
            break
    return markup.markdown(result)

@register.filter
@stringfilter
def first_upper(value):
    u"""Filter for formatting the value to set the first character to uppercase.
    """
    if value:
        return samples.views.utils.capitalize_first_letter(value)

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
        verbose_name = samples.views.utils.capitalize_first_letter(verbose_name)
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
        return u"""<td class="label">{label}:</td><td class="value">{value}</td>""".format(
            label=verbose_name, value=field if unit is None else quantity(field, unit))


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


@register.simple_tag
def split_field(field1, field2, separator=""):
    u"""Tag for combining two input fields wich have the same label and help text.
    It consists of two ``<td>`` elements, one for the label and one for
    the two input fields, so it spans two columns.  This tag is primarily used in
    tamplates of edit views.  Example::

        {% split_field layer.voltage1 layer.voltage2 "/" %}
    """
    result = u"""<td class="label"><label for="id_{html_name}">{label}:</label></td>""".format(
        html_name=field1.html_name, label=field1.label)
    help_text = u""" <span class="help">({0})</span>""".format(field1.help_text) if field1.help_text else u""
    result += u"""<td class="input">{field1}{separator}{field2}{help_text}</td>""".format(
        field1=field1, field2=field2, help_text=help_text, separator=separator)
    return result

class ValueSplitFieldNode(template.Node):
    u"""Helper class to realise the `value_split_field` tag.
    """

    def __init__(self, field1, field2, unit, separator):
        self.field_name1 = field1
        self.field_name2 = field2
        self.field1 = template.Variable(field1)
        self.field2 = template.Variable(field2)
        self.separator = separator if separator is not None else ''
        self.unit = unit

    def render(self, context):
        field1 = self.field1.resolve(context)
        field2 = self.field2.resolve(context)
        if "." not in self.field_name1:
            verbose_name = unicode(context[self.field_name1]._meta.verbose_name)
        else:
            instance, field_name = self.field_name1.rsplit(".", 1)
            model = context[instance].__class__
            verbose_name = unicode(model._meta.get_field(field_name).verbose_name)
        verbose_name = samples.views.utils.capitalize_first_letter(verbose_name)
        if self.unit == "sccm_collapse":
            if not field1 and not field2:
                return u"""<td colspan="2"/>"""
            unit = "sccm"
        else:
            unit = self.unit
        if not field1 and field1 != 0:
            field1 = u"—"
        if not field2 and field2 != 0:
            field2 = u"—"
        if field1 == field2 == u"—":
            unit = None
        return u"""<td class="label">{label}:</td><td class="value">{value1} {separator} {value2}</td>""".format(
            label=verbose_name, value1=field1 if unit is None else quantity(field1, unit),
            value2=field2 if unit is None else quantity(field2, unit),
            separator=self.separator)


@register.tag
def value_split_field(parser, token):
    u"""Tag for combining two value fields wich have the same label and help text.
    It consists of two ``<td>`` elements, one for the label and one for
    the two value fields, so it spans two columns.This tag is primarily used in
    templates of show views, especially those used to compile the sample history.
    Example::

        {% value_split_field layer.voltage_1 layer.voltage_2 "/" "V" %}

    The unit (``"V"`` for “Volt”) is optional.  If you have a boolean field,
    you can give ``"yes/no"`` as the unit, which converts the boolean value to
    a yes/no string (in the current language).  For gas flow fields that should
    collapse if the gas wasn't used, use ``"sccm_collapse"``.
    """
    tokens = token.split_contents()
    if len(tokens) == 5:
        tag, field1, field2, separator, unit = tokens
        if not (unit[0] == unit[-1] and unit[0] in ('"', "'")):
            raise template.TemplateSyntaxError, "value_split_field's unit argument should be in quotes"
        unit = unit[1:-1]
        if not (separator[0] == separator[-1] and separator[0] in ('"', "'")):
            raise template.TemplateSyntaxError, "value_split_field's separator argument should be in quotes"
        separator = separator[1:-1]
    elif len(tokens) == 4:
        tag, field1, field2, separator = tokens
        unit = None
        separator = separator[1:-1]
    elif len(tokens) == 3:
        tag, field1, field2 = tokens
        separator = None
        unit = None
    else:
        raise template.TemplateSyntaxError, "value_split_field requires three, four or five arguments"
    return ValueSplitFieldNode(field1, field2, unit, separator)
