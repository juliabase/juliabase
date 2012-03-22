#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Collection of tags and filters that I found useful for Chantal.
"""

from __future__ import division, unicode_literals
import string, re, sys, decimal
from django.template.defaultfilters import stringfilter
from django import template
from django.template.loader import render_to_string
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
from samples.views.form_utils import time_pattern
import chantal_common.search

register = template.Library()

# FixMe: An audit must be made to see where variable content is not properly
# escaped.  Candidates are input_field and ValueFieldNode, but there are
# probably other, too.


@register.filter
def round(value, digits):
    """Filter for rounding a numeric value to a fixed number of significant
    digits.  The result may be used for the `quantity` filter below.
    """
    return samples.views.utils.round(value, digits)


@register.filter
def quantity(value, unit=None, autoescape=False):
    """Filter for pretty-printing a physical quantity.  It converts 3.4e-3
    into 3.4·10⁻³.  The number is the part that is actually filtered, while the
    unit is the optional argument of this filter.  So, you may write::

        {{ deposition.pressure|quantity:"mbar" }}

    It is also possible to give a list of two values.  This is formatted in a
    from–to notation.
    """
    def pretty_print_number(number):
        """Pretty-print a single value.  For the from–to notation, this
        function is called twice.
        """
        if isinstance(number, float):
            value_string = "{0:g}".format(number)
        elif isinstance(number, decimal.Decimal):
            value_string = "{0:g}".format(float(number))
        else:
            value_string = unicode(number)
        if autoescape:
            value_string = conditional_escape(value_string)
        result = ""
        match = re.match(r"(?P<leading>.*?)(?P<prepoint>[-+]?\d*)(\.(?P<postpoint>\d+))?"
                         r"([Ee](?P<exponent>[-+]?\d+))?(?P<trailing>.*)", value_string)
        match_dict = match.groupdict("")
        result = match_dict["leading"] + match_dict["prepoint"].replace("-", "−")
        if match_dict["postpoint"]:
            result += "." + match_dict["postpoint"]
        if match_dict["exponent"]:
            result += " · 10<sup>"
            match_exponent = re.match(r"(?P<sign>[-+])?0*(?P<digits>\d+)", match_dict["exponent"])
            if match_exponent.group("sign") == "-":
                result += "−"
            result += match_exponent.group("digits")
            result += "</sup>"
        result += match_dict["trailing"]
        return result

    if value is None:
        return None
    if isinstance(value, (tuple, list)):
        result = "{0}–{1}".format(pretty_print_number(value[0]), pretty_print_number(value[1]))
    else:
        result = pretty_print_number(value)
    if autoescape:
        unit = conditional_escape(unit) if unit else None
    if unit:
        if unit[0] in "0123456789":
            result += " · " + unit
        else:
            result += " " + unit
    return mark_safe(result)
quantity.needs_autoescape = True


@register.filter
def should_show(operator):
    """Filter to decide whether an operator should be shown.  The operator
    should not be shown if it is an administrative account, i.e. an account
    that should not be visible except for administrators.
    """
    return not isinstance(operator, django.contrib.auth.models.User) or not operator.chantal_user_details.is_administrative


class VerboseNameNode(template.Node):
    """Helper class for the tag `verbose_name`.  While `verbose_name` does the
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
            return ""
        verbose_name = unicode(model._meta.get_field(field).verbose_name)
        if verbose_name:
            verbose_name = samples.views.utils.capitalize_first_letter(verbose_name)
        return verbose_name


@register.tag
def verbose_name(parser, token):
    """Tag for retrieving the descriptive name for an instance attribute.  For
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
    """Unfortunately, Django's get_full_name method for users returns the
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
            return mark_safe('<a href="{0}">{1}</a>'.format(django.core.urlresolvers.reverse(
                        "samples.views.external_operator.show", kwargs={"external_operator_id": user.pk}), full_name))
        elif anchor_type == "mailto":
            return mark_safe('<a href="mailto:{0}">{1}</a>'.format(user.email, full_name))
        elif anchor_type == "plain":
            return mark_safe(full_name)
        else:
            return ""
    return ""

get_really_full_name.needs_autoescape = True


@register.filter
def get_safe_operator_name(user, autoescape=False):
    """Return the name of the operator (with the markup generated by
    `get_really_full_name` and the ``"http"`` option) unless it is a
    confidential external operator.
    """
    if isinstance(user, django.contrib.auth.models.User) or \
            (isinstance(user, samples.models.ExternalOperator) and not user.confidential):
        return get_really_full_name(user, "http", autoescape)
    name = _("Confidential operator #{number}").format(number=user.pk)
    if autoescape:
        name = conditional_escape(name)
    return mark_safe('<a href="{0}">{1}</a>'.format(django.core.urlresolvers.reverse(
                "samples.views.external_operator.show", kwargs={"external_operator_id": user.pk}), name))

get_safe_operator_name.needs_autoescape = True


timestamp_formats = ("%Y-%m-%d %H:%M:%S",
                     "%Y-%m-%d %H:%M",
                         # Translators: Only change the <sup>h</sup>!
                     _("%Y-%m-%d %H<sup>h</sup>"),
                     "%Y-%m-%d",
                         # Translators: Only change order and punctuation
                     _("%b %Y"),
                     "%Y",
                     _("date unknown"))

@register.filter
def timestamp(value, minimal_inaccuracy=0):
    """Filter for formatting the timestamp of a process properly to reflect
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
    return mark_safe(chantal_common.utils.unicode_strftime(timestamp_,
                                                           timestamp_formats[max(int(minimal_inaccuracy), inaccuracy)]))


@register.filter
def status_timestamp(value, type_):
    """Filter for formatting the timestamp of a status message properly to
    reflect the inaccuracy connected with this timestamp.

    :Parameters:
      - `value`: the status message timestamp should be formatted
      - `type_`: either ``"begin"`` or ``"end"``

    :type value: ``samples.views.status.Status``
    :type type_: str

    :Return:
      the rendered timestamp

    :rtype: unicode
    """
    if type_ == "begin":
        timestamp_ = value.begin
        inaccuracy = value.begin_inaccuracy
    elif type_ == "end":
        timestamp_ = value.end
        inaccuracy = value.end_inaccuracy
    if inaccuracy == 6:
        return None
    return mark_safe(chantal_common.utils.unicode_strftime(timestamp_, timestamp_formats[inaccuracy]))


# FixMe: This pattern should probably be moved to settings.py.
sample_name_pattern = \
    re.compile(r"""(\W|\A)(?P<name>[0-9][0-9][A-Z]-[0-9]{3,4}([-A-Za-z_/][-A-Za-z_/0-9#]*)?|  # old-style sample name
                            ([0-9][0-9]-([A-Z]{2}[0-9]{,2}|[A-Z]{3}[0-9]?|[A-Z]{4})|           # initials of a user
                            [A-Z]{2}[0-9][0-9]|[A-Z]{3}[0-9]|[A-Z]{4})                         # initials of an external
                            -[-A-Za-z_/0-9#]+)(\W|\Z)""", re.UNICODE | re.VERBOSE)
sample_series_name_pattern = re.compile(r"(\W|\A)(?P<name>[a-z_]+-[0-9][0-9]-[-A-Za-zÄÖÜäöüß_/0-9]+)(\W|\Z)", re.UNICODE)

@register.filter
@stringfilter
def markdown_samples(value, margins="default"):
    """Filter for formatting the value by assuming Markdown syntax.
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
    result = ""
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
    result = markup.markdown(result)
    if result.startswith("<p>"):
        if margins == "collapse":
            result = mark_safe("""<p style="margin: 0pt">""" + result[3:])
    return result


@register.filter
@stringfilter
def prepend_domain(value):
    """Prepend the domain to an absolute URL without domain.
    """
    assert value[0] == "/"
    prefix = "http://" + settings.DOMAIN_NAME
    return prefix + value


@register.filter
@stringfilter
def first_upper(value):
    """Filter for formatting the value to set the first character to uppercase.
    """
    if value:
        return samples.views.utils.capitalize_first_letter(value)


@register.filter
@stringfilter
def flatten_multiline_text(value, separator=" ● "):
    """Converts a multiline string into a one-line string.  The lines are
    separated by big bullets, however, you can change that with the optional
    parameter.
    """
    lines = [line.strip() for line in value.strip().split("\n")]
    return separator.join(line for line in lines if line)


@register.filter
def sample_tags(sample, user):
    """Shows the sample's tags.  The tags are shortened.  Moreover, they are
    suppressed if the user is not allowed to view them.
    """
    return sample.tags_suffix(user)


class ValueFieldNode(template.Node):
    """Helper class to realise the `value_field` tag.
    """

    def __init__(self, field, unit, significant_digits):
        self.field_name = field
        self.field = template.Variable(field)
        self.unit = unit
        self.significant_digits = significant_digits

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
            field = get_really_full_name(field, autoescape=True)
            unit = None
        elif self.unit == "sccm_collapse":
            if not field:
                return """<td colspan="2"></td>"""
            unit = "sccm"
        elif not field and field != 0:
            unit = None
            field = "—"
        else:
            unit = self.unit
        if self.significant_digits and field != "—":
            field = round(field, self.significant_digits)
        return """<td class="label">{label}:</td><td class="value">{value}</td>""".format(
            label=verbose_name, value=conditional_escape(field) if unit is None else quantity(field, unit))


@register.tag
def value_field(parser, token):
    """Tag for inserting a field value into an HTML table.  It consists of two
    ``<td>`` elements, one for the label and one for the value, so it spans two
    columns.  This tag is primarily used in templates of show views, especially
    those used to compile the sample history.  Example::

        {% value_field layer.base_pressure "W" 3 %}

    The unit (``"W"`` for “Watt”) is optional.  If you have a boolean field,
    you can give ``"yes/no"`` as the unit, which converts the boolean value to
    a yes/no string (in the current language).  For gas flow fields that should
    collapse if the gas wasn't used, use ``"sccm_collapse"``.

    The number 3 is also optional.  However, if it is set, the unit must be at
    least ``""``.  With this option you can set the number of significant
    digits of the value.  The value will be rounded to match the number of
    significant digits.
    """
    tokens = token.split_contents()
    if len(tokens) == 4:
        tag, field, unit, significant_digits = tokens
        if not (unit[0] == unit[-1] and unit[0] in ('"', "'")):
            raise template.TemplateSyntaxError, "value_field's unit argument should be in quotes"
        unit = unit[1:-1]
    elif len(tokens) == 3:
        tag, field, unit = tokens
        significant_digits = None
        if not (unit[0] == unit[-1] and unit[0] in ('"', "'")):
            if not isinstance(unit, int):
                raise template.TemplateSyntaxError, "value_field's unit argument should be in quotes"
            else:
                significant_digits = unit
                unit = None
        else:
            unit = unit[1:-1]
    elif len(tokens) == 2:
        tag, field = tokens
        unit = significant_digits = None
    else:
        raise template.TemplateSyntaxError, "value_field requires one, two, or three arguments"
    return ValueFieldNode(field, unit or None, significant_digits)


@register.simple_tag
def split_field(field1, field2, field3=None):
    """Tag for combining two or three input fields wich have the same label
    and help text.  It consists of two or three ``<td>`` elements, one for the
    label and one for the input fields, so it spans multiple columns.  This tag
    is primarily used in templates of edit views.  Example::

        {% split_field layer.voltage1 layer.voltage2 %}

    The tag assumes that for from–to fields, the field name of the upper limit
    must end in ``"_end"``, and for ordinary multiple fields, the verbose name
    of the first field must end in a space-separated number or letter.  For
    example, the verbose names may be ``"voltage 1"``, ``"voltage 2"``, and
    ``"voltage 3"``.
    """
    from_to_field = not field3 and field2.html_name.endswith("_end")
    separator = " – " if from_to_field else " / "
    result = """<td class="label"><label for="id_{html_name}">{label}:</label></td>""".format(
        html_name=field1.html_name, label=field1.label if from_to_field else field1.label.rpartition(" ")[0])
    help_text = """ <span class="help">({0})</span>""".format(field1.help_text) if field1.help_text else ""
    fields = [field1, field2, field3]
    result += """<td class="input">{fields_string}{help_text}</td>""".format(
        fields_string=separator.join(unicode(field) for field in fields if field), help_text=help_text)
    return result


class ValueSplitFieldNode(template.Node):
    """Helper class to realise the `value_split_field` tag.
    """

    def __init__(self, fields, unit):
        self.field_name = fields[0]
        self.from_to_field = len(fields) == 2 and fields[1].endswith("_end")
        self.fields = [template.Variable(field) for field in fields]
        self.unit = unit

    def render(self, context):
        fields = [field.resolve(context) for field in self.fields]
        if "." not in self.field_name:
            verbose_name = unicode(context[self.field_name]._meta.verbose_name)
        else:
            instance, __, field_name = self.field_name.rpartition(".")
            model = context[instance].__class__
            verbose_name = unicode(model._meta.get_field(field_name).verbose_name)
        verbose_name = samples.views.utils.capitalize_first_letter(verbose_name)
        if self.unit == "sccm_collapse":
            if all(field is None for field in fields):
                return """<td colspan="2"></td>"""
            unit = "sccm"
        else:
            unit = self.unit
        if self.from_to_field:
            if fields[0] is None and fields[1] is None:
                values = "—"
            elif fields[1] is None:
                values = quantity(fields[0], unit)
            else:
                values = quantity(fields, unit)
        else:
            if verbose_name.endswith(" 1"):
                verbose_name = verbose_name[:-2]
            for i in range(len(fields)):
                if not fields[i] and fields[i] != 0:
                    fields[i] = "—"
            if all(field == "—" for field in fields):
                unit = None
            values = ""
            for field in fields[:-1]:
                if field == "—":
                    values += "— / "
                else:
                    values += quantity(field) + " / "
            values += unicode(fields[-1]) if unit is None else quantity(fields[-1], unit)
        return """<td class="label">{label}:</td><td class="value">{values}</td>""".format(
            label=verbose_name, values=values)


@register.tag
def value_split_field(parser, token):
    """Tag for combining two or more value fields wich have the same label and
    help text.  It consists of two ``<td>`` elements, one for the label and one
    for the value fields, so it spans two columns.  This tag is primarily used
    in templates of show views, especially those used to compile the sample
    history.  Example::

        {% value_split_field layer.voltage_1 layer.voltage_2 "V" %}

    The unit (``"V"`` for “Volt”) is optional.  If you have a boolean field,
    you can give ``"yes/no"`` as the unit, which converts the boolean value to
    a yes/no string (in the current language).  For gas flow fields that should
    collapse if the gas wasn't used, use ``"sccm_collapse"``.
    """
    tokens = token.split_contents()
    fields = []
    unit = None
    for i, token in enumerate(tokens):
        if i > 0:
            if token[0] == token[-1] and token[0] in ('"', "'"):
                if i < len(tokens) - 1:
                    raise template.TemplateSyntaxError, "the unit must be the very last argument"
                unit = token[1:-1]
            else:
                fields.append(token)
    return ValueSplitFieldNode(fields, unit)


@register.simple_tag
def display_search_tree(tree):
    """Tag for displaying the forms tree for the advanced search.  This tag is
    used only in the advanced search.  It walks through the search node tree
    and displays the seach fields.
    """
    result = """<table style="border: 2px solid black; padding-left: 3em"><tbody>"""
    for search_field in tree.search_fields:
        error_context = {"form": search_field.form, "form_error_title": _("General error"), "outest_tag": "<tr>"}
        result += render_to_string("error_list.html", context_instance=template.Context(error_context))
        if isinstance(search_field, chantal_common.search.RangeSearchField):
            field_min = [field for field in search_field.form if field.name.endswith("_min")][0]
            field_max = [field for field in search_field.form if field.name.endswith("_max")][0]
            help_text = """ <span class="help">({0})</span>""".format(field_min.help_text) if field_min.help_text else ""
            result += """<tr><td class="label"><label for="id_{html_name}">{label}:</label></td>""" \
                """<td class="input">{field_min} – {field_max}{help_text}</td></tr>""".format(
                label=field_min.label, html_name=field_min.html_name, field_min=field_min, field_max=field_max,
                help_text=help_text)
        elif isinstance(search_field, chantal_common.search.TextNullSearchField):
            field_main = [field for field in search_field.form if field.name.endswith("_main")][0]
            field_null = [field for field in search_field.form if field.name.endswith("_null")][0]
            help_text = """ <span class="help">({0})</span>""".format(field_main.help_text) if field_main.help_text else ""
            result += """<tr><td class="label"><label for="id_{html_name_main}">{label_main}:</label></td>""" \
                """<td class="input">{field_main} <label for="id_{html_name_null}">{label_null}:</label> """ \
                """{field_null}{help_text}</td></tr>""".format(
                label_main=field_main.label, label_null=field_null.label,
                html_name_main=field_main.html_name, html_name_null=field_null.html_name,
                field_main=field_main, field_null=field_null, help_text=help_text)
        else:
            for field in search_field.form:
                help_text = """ <span class="help">({0})</span>""".format(field.help_text) if field.help_text else ""
                result += """<tr><td class="label"><label for="id_{html_name}">{label}:</label></td>""" \
                    """<td class="input">{field}{help_text}</td></tr>""".format(
                    label=field.label, html_name=field.html_name, field=field, help_text=help_text)
    if tree.children:
        result += """<tr><td colspan="2">"""
        for i, child in enumerate(tree.children):
            result += unicode(child[0].as_p())
            if child[1]:
                result += display_search_tree(child[1])
            if i < len(tree.children) - 1:
                result += """</td></tr><tr><td colspan="2">"""
        result += "</td></tr>"
    result += "</tbody></table>"
    return result


@register.filter
@stringfilter
def hms_to_minutes(time_string):
    """Converts ``"01:01:02"`` to ``"61.03"``.
    """
    match = time_pattern.match(time_string)
    if not match:
        return time_string
    minutes = int(match.group("H") or "0") * 60 + int(match.group("M")) + int(match.group("M")) / 60
    return round(minutes, 2)


@register.simple_tag
def lab_notebook_comments(process, position):
    """This tag allows to set a stand-alone comment in a lab notebook.
    The comment string will be extracted from the process comment and should be placed
    before or after the process.
    The argument ``position`` must be ``before`` or ``after`` to specify the position
    related to the process.

    :Parameters:
     -`process`: the actual process instance
     -`position`: the argument to specify whether the comment is set
     before or after the process.

    :type process: ``models.Process``
    :type position: str
    """
    if position.lower() == "before":
        keyword = "BEFORE:"
        try:
            start_index = process.comments.index(keyword) + len(keyword)
        except ValueError:
            return ""
        try:
            keyword = "AFTER:"
            end_index = process.comments.index(keyword)
        except ValueError:
            end_index = len(process.comments)
    elif position.lower() == "after":
        keyword = "AFTER:"
        try:
            start_index = process.comments.index(keyword) + len(keyword)
        except ValueError:
            return ""
        end_index = len(process.comments)
    else:
        return ""
    notebook_comment = """<tr style="vertical-align: top"><td colspan="100" class="top" style="text-align: center">{0}</td></tr>""" \
        .format(markdown_samples(process.comments[start_index: end_index].strip()))
    return mark_safe(notebook_comment)


@register.filter
def task_color(task):
    """Returns the colour which is associated with the status of the task.
    The returned string is ready-to-be-used in CSS directives as
    a colour hex code.
    """
    return {"0 finished": "#90EE90", "1 new": "#D0D0D0", "2 accepted": "#ADD8E6", "3 in progress": "#FFCC66"}[task.status]


@register.filter
def get_hash_value(instance):
    """
    """
    return instance.get_hash_value()
