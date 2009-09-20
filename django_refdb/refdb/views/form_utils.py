#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Utility classes and routines for form handling.
"""

from __future__ import absolute_import

from django.forms.util import ErrorList


def append_error(form, error_message, fieldname="__all__"):
    u"""This function is called if a validation error is found in form data
    which cannot be found by the ``is_valid`` method itself.  The reason is
    very simple: For many types of invalid data, you must take other forms in
    the same view into account.

    :Parameters:
      - `form`: the form to which the erroneous field belongs
      - `error_message`: the message to be presented to the user
      - `fieldname`: the name of the field that triggered the validation
        error.  It is optional, and if not given, the error is considered an
        error of the form as a whole.

    :type form: ``forms.Form`` or ``forms.ModelForm``.
    :type fieldname: str
    :type error_message: unicode
    """
    # FixMe: Is it really a good idea to call ``is_valid`` here?
    # ``append_error`` is also called in ``clean`` methods after all.
    form.is_valid()
    form._errors.setdefault(fieldname, ErrorList()).append(error_message)
