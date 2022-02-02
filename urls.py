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


"""Root URL dispach for the JuliaBase installation.  Mapping URL patterns to
function calls.  This is the local URL dispatch of the Django application
“jb_common”, which provides core functionality and core views for all JuliaBase
apps.

:var urlpatterns: the actual mapping.  See the `Django documentation`_ for
  details.

.. _Django documentation:
    http://docs.djangoproject.com/en/dev/topics/http/urls/
"""

from django.urls import include, re_path
from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
import oai_pmh.urls, institute.urls, jb_common.urls, samples.urls


urlpatterns = [
#    re_path(r"^oai-pmh", include(oai_pmh.urls)),
    re_path(r"", include(institute.urls)),
    re_path(r"", include(jb_common.urls)),
    re_path(r"", include(samples.urls)),

    re_path(r"^admin/", admin.site.urls),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
