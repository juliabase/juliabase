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


"""General helper functions.  This is for low-level stuff.  Never import other
JuliaBase modules here, and avoid using Django, too.  The reason is that I'd
like to avoid cyclic imports, and I'd like to avoid being forced to ship the
whole of Django with the Remove Client (which uses this module).

Note that all names defined here are also available in `utils`, so this module
is really only interesting for the Remote Client.

Important: A *copy* of this module is bundled with the remote client, which is
part of the institute-specific package.  So synchronise it now and then with
its copy there.
"""

from __future__ import absolute_import, unicode_literals

import re, string, codecs, os, os.path
