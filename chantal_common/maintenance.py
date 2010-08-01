#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


u"""Module for providing the maintenance signal.  This is sent in regular time
intervals (e.g., every night), so that various subsystems can use it for
maintenance work.  You can use this signal in your code like this::

    from chantal_common.maintenance import maintain

    def my_handler(sender, **kwargs):
        ...

    maintain.connect(my_handler, sender=None)
"""

from __future__ import absolute_import

import django.dispatch
import chantal_common


maintain = django.dispatch.Signal()
