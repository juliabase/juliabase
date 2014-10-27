#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

"""The settings for the remote client.  If you want to change them in an
institute-specific module, just import this one with::

    from jb_remote import settings

and change the settings like this::

    settings.root_url = "https://juliabase.ipv.kfa-juelich.de/"

It is important to change the settings before the login into JuliaBase takes
place.
"""

from __future__ import absolute_import, unicode_literals, division

# Must end in "/".
root_url = "https://juliabase.my_institute.kfa-juelich.de/"
testserver_root_url = "https://test-jb.my_institute.kfa-juelich.de/"

smtp_server = "mailrelay.example.com:587"
# If not empty, TLS is used.
smtp_login = "username"
smtp_password = "password"
email_from = "me@example.com"
email_to = "admins@example.com"
