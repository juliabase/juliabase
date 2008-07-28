#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string, re
from django.template.defaultfilters import stringfilter
from django import template
from django.utils.html import conditional_escape
import django.utils.safestring
import chantal.samples.models, django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _

register = template.Library()

@register.filter
@stringfilter
def chem_markup(chemical_formula, autoescape=False):
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
    return django.utils.safestring.mark_safe(result)
chem_markup.needs_autoescape = True

@register.filter
def quantity(value, unit=None, autoescape=False):
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
    return django.utils.safestring.mark_safe(result)
chem_markup.needs_autoescape = True

@register.filter
def fancy_bool(boolean):
    result = _(u"Yes") if boolean else _(u"No")
    return django.utils.safestring.mark_safe(result)

class VerboseNameNode(template.Node):
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
    tag_name, var = token.split_contents()
    return VerboseNameNode(var)
