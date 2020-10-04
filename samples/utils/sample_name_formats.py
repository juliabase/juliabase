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


"""Helper functions concerning sample name formats.
"""

from django.conf import settings


def verbose_sample_name_format(name_format):
    """Returns the human-friendly, translatable name of the sample name format.  In
    English, it is in singular, and usable as an attribute to a noun.  In
    non-English language, you should choose something equivalent for the
    translation.

    :param name_format: The name format

    :type name_format: str

    :return:
      The verbose human-friendly name of this sample name format.

    :rtype: str
    """
    return settings.SAMPLE_NAME_FORMATS[name_format]["verbose_name"]


def sample_name_format(name, with_match_object=False):
    """Determines which sample name format the given name has.  It doesn't test
    whether the sample name is existing, nor if the initials are valid.

    :param name: the sample name

    :type name: str

    :return:
      The name of the sample name format and the respective match object.  The
      latter can be used to extract groups, for exampe.  ``None`` if the name
      had no valid format.

    :rtype: (str, re.MatchObject) or NoneType.
    """
    for name_format, properties in settings.SAMPLE_NAME_FORMATS.items():
        match = properties["regex"].match(name)
        if match:
            return (name_format, match) if with_match_object else name_format
    return (None, None) if with_match_object else None


renamable_name_formats = None
def get_renamable_name_formats():
    global renamable_name_formats
    if renamable_name_formats is None:
        renamable_name_formats = {name_format for (name_format, properties) in settings.SAMPLE_NAME_FORMATS.items()
                                  if properties.get("possible_renames")}
    return renamable_name_formats
