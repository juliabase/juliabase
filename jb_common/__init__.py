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


"""
The error codes for a JSON client are the following:

    ======= ===============================================
    code    description
    ======= ===============================================
    1       Web form error
    2       URL not found, i.e. only with HTTP 404
    3       GET/POST parameter missing
    4       user could not be authenticated
    5       GET/POST parameter invalid
    6       Access denied
    ======= ===============================================
"""


default_app_config = "jb_common.apps.JBCommonConfig"

__version__ = "1.0"
