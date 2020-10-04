# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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

import re, sys, decimal, math
import markdown
from django.template.defaultfilters import stringfilter
from django import template
from django.template.loader import render_to_string
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.contrib.staticfiles.storage import staticfiles_storage
import django.utils.http
import django.utils.timezone
import django.urls
import samples.models, django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.conf import settings
import jb_common.utils.base
import jb_common.templatetags.juliabase
import jb_common.search
import samples.utils.views
import samples.utils.sample_names


register = template.Library()

# FixMe: An audit must be made to see where variable content is not properly
# escaped.  Candidates are input_field and ValueFieldNode, but there are
# probably other, too.


@register.filter
def round(value, digits):
    """Filter for rounding a numeric value to a fixed number of significant digits.
    The result may be used for the :py:func:`quantity` filter below.
    """
    return jb_common.utils.base.round(value, digits)


@register.filter(needs_autoescape=True)
def quantity(value, unit=None, autoescape=False):
    """Filter for pretty-printing a physical quantity.  It converts ``3.4e-3`` into
    :math:`3.4\\cdot10^{-3}`.  The number is the part that is actually filtered, while the
    unit is the optional argument of this filter.  So, you may write::

        {{ deposition.pressure|quantity:"mbar" }}

    It is also possible to give a list of two values.  This is formatted in a
    from–to notation.
    """
    def pretty_print_number(number):
        """Pretty-print a single value.  For the from–to notation, this
        function is called twice.
        """
        if isinstance(number, (float, decimal.Decimal)):
            if number == 0 or -2 <= math.log10(abs(number)) < 5:
                value_string = "{0:g}".format(float(number))
            else:
                value_string = "{0:e}".format(float(number))
        else:
            value_string = str(number)
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


@register.filter
def should_show(operator):
    """Filter to decide whether an operator should be shown.  The operator should
    not be shown if they are in no department because this is considered not an
    account of an actual person.
    """
    return not isinstance(operator, django.contrib.auth.models.User) or operator.jb_user_details.department


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
        verbose_name = str(model._meta.get_field(field).verbose_name)
        if verbose_name:
            verbose_name = jb_common.utils.base.capitalize_first_letter(verbose_name)
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
def get_really_full_name(user, anchor_type="http"):
    """Unfortunately, Django's get_full_name method for users returns the empty
    string if the user has no first and surname set. However, it'd be sensible
    to use the login name as a fallback then. This is realised here.  See also
    :py:func:`samples.utils.views.get_really_full_name`.

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
    if isinstance(user, django.contrib.auth.models.User):
        return jb_common.templatetags.juliabase.get_really_full_name(user, anchor_type)
    elif isinstance(user, samples.models.ExternalOperator):
        full_name = user.name
        if anchor_type == "http":
            return format_html('<a href="{0}">{1}</a>', mark_safe(django.urls.reverse(
                "samples:show_external_operator", kwargs={"external_operator_id": user.pk})), full_name)
        elif anchor_type == "mailto":
            return format_html('<a href="mailto:{0}">{1}</a>', user.email, full_name)
        elif anchor_type == "plain":
            return full_name
        else:
            return ""
    return ""


@register.filter
def get_safe_operator_name(user):
    """Return the name of the operator (with the markup generated by
    `get_really_full_name` and the ``"http"`` option) unless it is a
    confidential external operator.
    """
    if isinstance(user, django.contrib.auth.models.User) or \
            (isinstance(user, samples.models.ExternalOperator) and not user.confidential):
        return get_really_full_name(user, "http")
    name = _("Confidential operator #{number}").format(number=user.pk)
    return format_html('<a href="{0}">{1}</a>', mark_safe(django.urls.reverse(
        "samples:show_external_operator", kwargs={"external_operator_id": user.pk})), name)


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
    """Filter for formatting the timestamp of a process properly to reflect the
    inaccuracy connected with this timestamp.  It works not strictly only for
    models.  In fact, any object with a ``timestamp`` field can be passed in.
    If no ``timestamp_inaccuracy`` field is present in the value, 0 (accuracy
    to the second) is assumed.

    Instead of a model instance, a dict objects may be used as the input value.
    In this case, keys instead of attributes are looked up, but with the same
    names.

    :param value: the model whose timestamp should be formatted
    :param minimal_inaccuracy: minimal inaccuracy used for display

    :type value: ``models.Model`` or dict mapping str to object
    :type minimal_inaccuracy: int

    :return:
      the rendered timestamp

    :rtype: str
    """
    try:
        timestamp_ = value.timestamp
        inaccuracy = getattr(value, "timestamp_inaccuracy", 0)
    except AttributeError:
        timestamp_ = value["timestamp"]
        inaccuracy = value.get("timestamp_inaccuracy", 0)
    timestamp_ = timestamp_.astimezone(django.utils.timezone.get_current_timezone())
    return mark_safe(timestamp_.strftime(str(timestamp_formats[max(int(minimal_inaccuracy), inaccuracy)])))


@register.filter
def status_timestamp(value, type_):
    """Filter for formatting the timestamp of a status message properly to
    reflect the inaccuracy connected with this timestamp.

    :param value: the status message timestamp should be formatted
    :param type_: either ``"begin"`` or ``"end"``

    :type value: ``samples.views.status.Status``
    :type type_: str

    :return:
      the rendered timestamp

    :rtype: str
    """
    if type_ == "begin":
        timestamp_ = value.begin
        inaccuracy = value.begin_inaccuracy
    elif type_ == "end":
        timestamp_ = value.end
        inaccuracy = value.end_inaccuracy
    if inaccuracy == 6:
        return None
    timestamp_ = timestamp_.astimezone(django.utils.timezone.get_current_timezone())
    return mark_safe(timestamp_.strftime(str(timestamp_formats[inaccuracy])))


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
    `samples.utils.views.substitute_html_entities`.  This creates a mild
    escaping problem.  ``\&amp;`` becomes ``&amp;amp;`` instead of ``\&amp;``.
    It can only be solved by getting python-markdown to replace the entities,
    however, I can't easily do that without allowing HTML tags, too.
    """
    value = jb_common.templatetags.juliabase.substitute_formulae(
        jb_common.utils.base.substitute_html_entities(str(value)))
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
                sample = samples.utils.sample_names.get_sample(name)
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
    result = markdown.markdown(result)
    if result.startswith("<p>"):
        if margins == "collapse":
            result = """<p style="margin: 0pt">""" + result[3:]
    return mark_safe(result)


@register.filter(is_safe=True)
@stringfilter
def first_upper(value):
    """Filter for formatting the value to set the first character to uppercase.
    """
    if value:
        return jb_common.utils.base.capitalize_first_letter(value)


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
    display_method_regex = re.compile(r"get_(?P<field_name>.*)_display$")

    def __init__(self, expression, unit, significant_digits):
        self.variable = expression.var.var
        self.expression = expression
        self.unit = unit
        self.significant_digits = significant_digits

    def render(self, context):
        value = self.expression.resolve(context)
        if "." not in self.variable:
            verbose_name = str(context[self.variable]._meta.verbose_name)
        else:
            instance, field_name = self.variable.rsplit(".", 1)
            match = self.display_method_regex.match(field_name)
            if match:
                field_name = match.group("field_name")
            model = context[instance].__class__
            model_field = model._meta.get_field(field_name)
            verbose_name = str(model_field.verbose_name)
            if self.unit is None:
                try:
                    self.unit = model_field.unit
                except AttributeError:
                    pass
        verbose_name = jb_common.utils.base.capitalize_first_letter(verbose_name)
        if self.unit == "yes/no":
            value = jb_common.templatetags.juliabase.fancy_bool(value)
            unit = None
        elif self.unit == "user":
            value = get_really_full_name(value)
            unit = None
        elif self.unit == "sccm_collapse":
            if not value:
                return """<td colspan="2"></td>"""
            unit = "sccm"
        elif not value and value != 0:
            unit = None
            value = "—"
        else:
            unit = self.unit
        if self.significant_digits and value != "—":
            value = jb_common.utils.base.round(value, self.significant_digits)
        return """<td class="field-label">{label}:</td><td class="field-value">{value}</td>""".format(
            label=verbose_name, value=conditional_escape(value) if unit is None else quantity(value, unit))


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
    collapse if the gas wasn't used, use ``"sccm_collapse"``.  If not given but
    the model field has a unit set (i.e. ``...QuantityField``), that unit is
    used.

    The number 3 is also optional.  However, if it is set, the unit must be at
    least ``""``.  With this option you can set the number of significant
    digits of the value.  The value will be rounded to match the number of
    significant digits.
    """
    tokens = token.split_contents()
    if len(tokens) == 4:
        tag, field, unit, significant_digits = tokens
        if not (unit[0] == unit[-1] and unit[0] in ('"', "'")):
            raise template.TemplateSyntaxError("value_field's unit argument should be in quotes")
        unit = unit[1:-1]
    elif len(tokens) == 3:
        tag, field, unit = tokens
        significant_digits = None
        if not (unit[0] == unit[-1] and unit[0] in ('"', "'")):
            if not isinstance(unit, int):
                raise template.TemplateSyntaxError("value_field's unit argument should be in quotes")
            else:
                significant_digits = unit
                unit = None
        else:
            unit = unit[1:-1]
    elif len(tokens) == 2:
        tag, field = tokens
        unit = significant_digits = None
    else:
        raise template.TemplateSyntaxError("value_field requires one, two, or three arguments")
    return ValueFieldNode(parser.compile_filter(field), unit or None, significant_digits)


@register.simple_tag
def split_field(*fields):
    """Tag for combining two or three input fields wich have the same label and
    help text.  It consists of three or more ``<td>`` elements, one for the
    label and one for the input fields (at least two), so it spans multiple
    columns.  This tag is primarily used in templates of edit views.  Example::

        {% split_field layer.voltage1 layer.voltage2 %}

    The tag assumes that for from–to fields, the field name of the upper limit
    must end in ``"_end"``, and for ordinary multiple fields, the verbose name
    of the first field must end in a space-separated number or letter.  For
    example, the verbose names may be ``"voltage 1"``, ``"voltage 2"``, and
    ``"voltage 3"``.
    """
    from_to_field = len(fields) == 2 and fields[1].html_name.endswith("_end")
    separator = " – " if from_to_field else " / "
    result = """<td class="field-label"><label for="{id_for_label}">{label}:</label></td>""".format(
        id_for_label=fields[0].id_for_label, label=fields[0].label if from_to_field else fields[0].label.rpartition(" ")[0])
    help_text = """ <span class="help">({0})</span>""".format(fields[0].help_text) if fields[0].help_text else ""
    result += """<td class="field-input">{fields_string}{help_text}</td>""".format(
        fields_string=separator.join(str(field) for field in fields), help_text=help_text)
    return mark_safe(result)


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
            verbose_name = str(context[self.field_name]._meta.verbose_name)
        else:
            instance, __, field_name = self.field_name.rpartition(".")
            model = context[instance].__class__
            model_field = model._meta.get_field(field_name)
            verbose_name = str(model_field.verbose_name)
            if self.unit is None:
                try:
                    self.unit = model_field.unit
                except AttributeError:
                    pass
        verbose_name = jb_common.utils.base.capitalize_first_letter(verbose_name)
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
            values += fields[-1] if fields[-1] == "—" else quantity(fields[-1], unit)
        return """<td class="field-label">{label}:</td><td class="field-value">{values}</td>""".format(
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
    collapse if the gas wasn't used, use ``"sccm_collapse"``.  If not given but
    the model field has a unit set (i.e. ``...QuantityField``), that unit is
    used.
    """
    tokens = token.split_contents()
    fields = []
    unit = None
    for i, token in enumerate(tokens):
        if i > 0:
            if token[0] == token[-1] and token[0] in ('"', "'"):
                if i < len(tokens) - 1:
                    raise template.TemplateSyntaxError("the unit must be the very last argument")
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
    result = """<table style="border: 2px solid black; padding-left: 3em">"""
    for search_field in tree.search_fields:
        error_context = {"form": search_field.form, "form_error_title": _("General error"), "outest_tag": "<tr>"}
        result += render_to_string("error_list.html", error_context)
        if isinstance(search_field, jb_common.search.RangeSearchField):
            field_min = [field for field in search_field.form if field.name.endswith("_min")][0]
            field_max = [field for field in search_field.form if field.name.endswith("_max")][0]
            help_text = """ <span class="help">({0})</span>""".format(field_min.help_text) if field_min.help_text else ""
            unit = """ <span class="help">{0}</span>""".format(search_field.field.unit) if hasattr(search_field.field, "unit") \
                and search_field.field.unit else ""
            result += """<tr><td class="field-label"><label for="{id_for_label}">{label}:</label></td>""" \
                """<td class="field-input">{field_min} – {field_max}{unit}{help_text}</td></tr>""".format(
                label=field_min.label, id_for_label=field_min.id_for_label, field_min=field_min, field_max=field_max,
                unit=unit, help_text=help_text)
        elif isinstance(search_field, jb_common.search.TextNullSearchField):
            field_main = [field for field in search_field.form if field.name.endswith("_main")][0]
            field_null = [field for field in search_field.form if field.name.endswith("_null")][0]
            help_text = """ <span class="help">({0})</span>""".format(field_main.help_text) if field_main.help_text else ""
            result += """<tr><td class="field-label">{label_tag_main}</td>""" \
                """<td class="field-input">{field_main} {label_tag_null} """ \
                """{field_null}{help_text}</td></tr>""".format(
                label_tag_main=field_main.label_tag(), label_tag_null=field_null.label_tag(),
                field_main=field_main, field_null=field_null, help_text=help_text)
        else:
            for field in search_field.form:
                help_text = """ <span class="help">({0})</span>""".format(field.help_text) if field.help_text else ""
                result += """<tr><td class="field-label">{label_tag}</td>""" \
                    """<td class="field-input">{field}{help_text}</td></tr>""".format(
                        label_tag=field.label_tag(), field=field, help_text=help_text)
    if tree.children:
        result += """<tr><td colspan="2">"""
        for i, child in enumerate(tree.children):
            result += child[0].as_p()
            if child[1]:
                result += display_search_tree(child[1])
            if i < len(tree.children) - 1:
                result += """</td></tr><tr><td colspan="2">"""
        result += "</td></tr>"
    result += "</table>"
    return mark_safe(result)


@register.filter
@stringfilter
def hms_to_minutes(time_string):
    """Converts ``"01:01:02"`` to ``"61.03"``.
    """
    match = samples.utils.views.time_pattern.match(time_string)
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

    :param process: the actual process instance
    :param position: the argument to specify whether the comment is set
        before or after the process.

    :type process: `samples.models.Process`
    :type position: str
    """
    if position.lower() == "before":
        keyword = "BEFORE:"
        try:
            start_index = process.comments.index(keyword) + len(keyword)
        except ValueError:
            return mark_safe("")
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
            return mark_safe("")
        end_index = len(process.comments)
    else:
        return mark_safe("")
    notebook_comment = """<tr style="vertical-align: top" class="topline">
                            <td colspan="100" style="text-align: center">{0}</td></tr>""" \
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
    return instance.get_hash_value()


@register.simple_tag
def expand_topic(topic, user):
    topic_id = topic.topic.id
    result = """<h3><img src="{group_icon_url}" alt="topic icon" style="margin-right: 0.5em" class="topics"
                   width="16" height="16" id="topic-image-{topic_id}"/>{topic_name}</h3>
            <div id="topic-{topic_id}">
            """.format(group_icon_url=staticfiles_storage.url("juliabase/icons/group.png"), topic_id=topic_id,
                       topic_name=topic.topic.name)
    if topic.samples:
        result += """<ul class="sample-list">
            """
        for sample in topic.samples:
            result += """<li><a href="{sample_url}">{sample}</a>{sample_tags}</li>
            """.format(sample_url=sample.get_absolute_url(), sample=sample, sample_tags=sample_tags(sample, user))
        result += """</ul>
            """
    result += """<div class="my-samples-series">
                """
    for series in topic.sample_series:
        result += """<h4><img src="{chart_icon_url}" alt="sample series icon" class="sample-series"
                         style="margin-right: 0.5em" width="16" height="16" id="series-image-{sample_series_hash_value}"
                         /><a href="{sample_series_url}">{series_name}</a></h4>""" \
                         """<div id="sample-series-{sample_series_hash_value}">
                         """.format(chart_icon_url=staticfiles_storage.url("juliabase/icons/chart_organisation.png"),
                                    sample_series_hash_value=get_hash_value(series.sample_series),
                                sample_series_url=series.sample_series.get_absolute_url(), series_name=series.name)
        if not series.is_complete:
            result += """<p>{translate}</p>""".\
            format(translate=_("(This series contains further samples not part of your “My Samples” list.)"))
        result += """<ul class="sample-list">                    """
        for sample in series.samples:
            result += """<li><a href="{sample_url}">{sample}</a>{sample_tags}</li>
            """.format(sample_url=sample.get_absolute_url(), sample=sample, sample_tags=sample_tags(sample, user))
        result += """</ul>
                  </div>
                  """
    result += """</div>
          """
    if topic.sub_topics:
        for i, sub_topic in enumerate(topic.sub_topics):
            result += """<div class="my-samples-topics" id="topic-{topic_id}-sub_topic-{sub_topic}">
            """.format(topic_id=topic_id, sub_topic=i)
            result += expand_topic(sub_topic, user)
            result += """</div>
            """
    result += """</div>
          """
    return mark_safe(result)


@register.filter
def class_name(value):
    """Returns the class name for a database model instance.
    """
    return value.__class__.__name__


@register.filter
def strip_substrings(value, pattern):
    """Removes substrings from a value.  The substring pattern should have a clear
    delimiter.

    The allowed delimiter “;”, “,” and “\t”.
    """
    for substring in re.split(r";|,|\t", pattern):
        substring = substring.strip()
        value = value.replace(substring, "")
    return value


@register.filter
def camel_case_to_human_text(value):
    """See `jb_common.utils.base.camel_case_to_human_text` for documentation.
    """
    return jb_common.utils.base.camel_case_to_human_text(value)


_ = ugettext
