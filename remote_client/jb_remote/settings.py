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

"""The settings for the remote client.  If you want to change them in an
institute-specific module, just import this one with::

    from jb_remote import settings

or::

    from jb_remote import *

and change the settings like this::

    settings.ROOT_URL = "https://my-juliabase-server.example.com/"

It is important to change the settings before the login into JuliaBase takes
place.
"""

import os
from pathlib import Path


# Must end in "/".
ROOT_URL = None
TESTSERVER_ROOT_URL = "https://demo.juliabase.org/"

SMTP_SERVER = "mailrelay.example.com:587"
# If not empty, TLS is used.
SMTP_LOGIN = "username"
SMTP_PASSWORD = "password"
EMAIL_FROM = "me@example.com"
EMAIL_TO = "admins@example.com"
CRAWLERS_DATA_DIR = Path(os.environ.get("CRAWLERS_DATA_DIR", "/var/lib/crawlers"))
