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

from __future__ import absolute_import, unicode_literals


default_app_config = "jb_common.apps.JBCommonConfig"

__version__ = "1.0"
