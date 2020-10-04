# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Helper classes and function for the views that are used for the institute.
It supplements :py:mod:`samples.views.form_utils` with institute specific
classes and functions.
"""

import re
from django.utils.translation import ugettext as _
from django.forms.utils import ValidationError


deposition_number_pattern = re.compile("\d\d[A-Z]-\d{3,4}$")
def clean_deposition_number_field(value, letter):
    """Checks wheter a deposition number given by the user in a form is a
    valid one.  Note that it does not check whether a deposition with this
    number already exists in the database.  It just checks the syntax of the
    number.

    :param value: the deposition number entered by the user
    :param letter: the single uppercase letter denoting the deposition system;
        it may also be a list containing multiple possibily letters

    :type value: str
    :type letter: str or list of str

    :return:
      the original `value` (unchanged)

    :rtype: str

    :raises ValidationError: if the deposition number was not a valid deposition
        number
    """
    if not deposition_number_pattern.match(value):
        # Translators: “YY” is year, “L” is letter, and “NNN” is number
        raise ValidationError(_("Invalid deposition number.  It must be of the form YYL-NNN."), code="invalid")
    if isinstance(letter, list):
        if value[2] not in letter:
            raise ValidationError(_("The deposition letter must be an uppercase “%(letter)s”."),
                                  params={"letter": ", ".join(letter)}, code="invalid")
    else:
        if value[2] != letter:
            raise ValidationError(_("The deposition letter must be an uppercase “%(letter)s”."), params={"letter": letter},
                                  code="invalid")
    return value
