#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Collection of tags and filters that I found useful for Chantal.
"""

from __future__ import division
import string, re
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import django.utils.http
import django.core.urlresolvers
import chantal.samples.models, django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _
import chantal.samples.views.utils

register = template.Library()

@register.filter
@stringfilter
def chem_markup(chemical_formula, autoescape=False):
    u"""Filter for pretty-printing of chemical formula.  It just puts numbers
    in subscripts.  Thus, H2O becoms H₂O.
    """
    if autoescape:
        chemical_formula = conditional_escape(chemical_formula)
    result = u""
    i = 0
    while i < len(chemical_formula):
        if i > 0 and chemical_formula[i] in string.digits and chemical_formula[i-1] in string.ascii_letters:
            result += "<sub>"
            while True:
                result += chemical_formula[i]
                i += 1
                if i >= len(chemical_formula) or chemical_formula[i] not in string.digits:
                    break
            result += "</sub>"
        else:
            result += chemical_formula[i]
            i += 1
    return mark_safe(result)
chem_markup.needs_autoescape = True

@register.filter
def quantity(value, unit=None, autoescape=False):
    u"""Filter for pretty-printing a physical quantity.  It converts 3.4e-3
    into 3.4·10⁻³.  The number is the part that is actually filtered, while the
    unit is the optional argument of this filter.  So, you may write::

        {{ deposition.pressure|quantity:"mbar" }}

    """
    if value is None:
        return None
    value_string = u"%g" % value
    if autoescape:
        value_string = conditional_escape(value_string)
        unit = conditional_escape(unit)
    result = u""
    i = 0
    match = re.match(ur"(?P<leading>.*?)(?P<prepoint>\d*)(\.(?P<postpoint>\d+))?(e(?P<exponent>[-+]?\d+))?(?P<trailing>.*)",
                     value_string)
    match_dict = match.groupdict(u"")
    result = match_dict["leading"] + match_dict["prepoint"]
    if match_dict["postpoint"]:
        result += "." + match_dict["postpoint"]
    if match_dict["exponent"]:
        result += u" · 10<sup>"
        match_exponent = re.match(ur"(?P<sign>[-+])?0*(?P<digits>\d+)", match_dict["exponent"])
        if match_exponent.group("sign") == "-":
            result += u"-"
        result += match_exponent.group("digits")
        result += u"</sup>"
    result += match_dict["trailing"]
    if unit:
        result += "&nbsp;" + unit
    return mark_safe(result)
chem_markup.needs_autoescape = True

@register.filter
def fancy_bool(boolean):
    u"""Filter for coverting a bool into a translated “Yes” or “No”.
    """
    result = _(u"Yes") if boolean else _(u"No")
    return mark_safe(result)

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

        {% verbose_name deposition.pressure %}

    will print “pressure”.  Note that it will be translated for a non-English
    user.  It is useful for creating labels.

    Currently, this tag supports all Chantal models as well as
    ``django.contrib.auth.models.User``.  Other models could be added
    manually.
    """
    tag_name, var = token.split_contents()
    return VerboseNameNode(var)

@register.filter
@stringfilter
def urlquote(value):
    u"""Filter for quoting strings so that they can be used as parts of URLs.
    Note that also slashs »/« are escaped.
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
    See also `models.get_really_full_name`.

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
    # anchor_type may be "http", "mailto", or "plain".
    if not isinstance(user, django.contrib.auth.models.User):
        return u""
    full_name = chantal.samples.models.get_really_full_name(user)
    if autoescape:
        full_name = conditional_escape(full_name)
    if anchor_type == "http":
        return mark_safe(u'<a href="%s">%s</a>' % (django.core.urlresolvers.reverse("samples.views.main.show_user",
                                                                                    kwargs={"login_name": user.username}),
                                                   full_name))
    elif anchor_type == "mailto":
        return mark_safe(u'<a href="mailto:%s">%s</a>' % (user.email, full_name))
    elif anchor_type == "plain":
        return mark_safe(full_name)
    else:
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
