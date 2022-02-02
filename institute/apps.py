# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2022 Forschungszentrum Jülich GmbH, Jülich, Germany
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

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _, gettext


class InstituteConfig(AppConfig):
    name = "institute"
    verbose_name = _("Institute")

    def ready(self):
        import institute.signals
        import warnings
        warnings.filterwarnings(
                'error', r"DateTimeField .* received a naive datetime",
                RuntimeWarning, r'django\.db\.models\.fields')

_ = gettext
