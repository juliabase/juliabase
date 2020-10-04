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


"""Default values of settings of the app "samples".
"""

from django.utils.translation import ugettext_lazy as _, ugettext

ADD_SAMPLES_VIEW = ""
CACHE_ROOT = "/tmp/juliabase_cache"
CRAWLER_LOGS_ROOT = ""
CRAWLER_LOGS_WHITELIST = []
INITIALS_FORMATS = {"user": {"pattern": r"[A-Z]{2,4}|[A-Z]{2,3}\d|[A-Z]{2}\d{2}",
                             "description": _("The initials start with two uppercase letters.  "
                                              "They contain uppercase letters and digits only.  Digits are at the end.")},
                    "external_contact": {"pattern": r"[A-Z]{4}|[A-Z]{3}\d|[A-Z]{2}\d{2}",
                                         "description": _("The initials start with two uppercase letters.  "
                                                          "They contain uppercase letters and digits only.  "
                                                          "Digits are at the end.  "
                                                          "The length is exactly 4 characters.")}
                    }
MERGE_CLEANUP_FUNCTION = ""
NAME_PREFIX_TEMPLATES = []
SAMPLE_NAME_FORMATS = {"provisional": {"possible_renames": {"default"}},
                       "default":     {"pattern": r"[-A-Za-z_/0-9#()]*"}}
THUMBNAIL_WIDTH = 400

# Django settings which are used in samples

# MEDIA_ROOT
# SECRET_KEY
# STATIC_ROOT
# STATIC_URL
# INSTALLED_APPS
# CACHES


_ = ugettext
