#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Module for providing the JuliaBase signals.

:ivar maintain: This is sent in regular time intervals (e.g., every night), so
  that various subsystems can use it for maintenance work.  You can use this
  signal in your code like this::

      from chantal_common.signals import maintain
      from django.dispatch import receiver

      @receiver(maintain)
      def my_handler(sender, **kwargs):
          ...


:ivar storage_changed: This is sent if the files on harddisk were changed.  In
  the reference deployment at IEK-5, this signal is used for triggering
  sychronisation of both nodes.
"""

from __future__ import absolute_import, unicode_literals

import django.dispatch


maintain = django.dispatch.Signal()

storage_changed = django.dispatch.Signal()
