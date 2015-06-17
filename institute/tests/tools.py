#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import absolute_import, unicode_literals

import re


def assertContainsError(test_case, response, heading, message="This field is required."):
    """Asserts that an error is reported in the response.  This error is shown
    in white on red on the web page, so we scan the HTML for it.

    :param test_case: current test case
    :param response: response object of the test case's HTTP client
    :param heading: The heading (a.k.a. label) of the error message.  For
      single fields, this is the name of the field, starting with an uppercase
      letter.  For non-field errors, it is the hardcoded label of the template,
      usually something like “Error in …”.
    :param message: the error message

    :type test_case: ``TestCase``
    :type response: ``django.http.HttpResponse``
    :type heading: str
    :type message: str
    """
    test_case.assertRegexpMatches(response.content,
                                  r"""<p>{}</p><ul class="errorlist( nonfield)?"><li>{}</li></ul>""".format(
                                      re.escape(heading), re.escape(message)),
                                  """No error message "{}" for "{}" found in response.""".format(message, heading))
