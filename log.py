#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
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


"""Custom logging class which doesn't send HTML emails.  This module must
reside on top-level because in institute, the settings would be implicitly imported,
which leads to a cyclic import.
"""

from __future__ import unicode_literals
import logging, sys
from django.core import mail


class AdminEmailHandler(logging.Handler):
    """Modified version of ``AdminEmailHandler`` in ``django/utils/log.py``.
    The only thing that is changed is that it doesn't send HTML parts in
    emails.
    """
    def emit(self, record):
        import traceback
        from django.conf import settings
        from django.views.debug import ExceptionReporter

        try:
            if sys.version_info < (2,5):
                # A nasty workaround required because Python 2.4's logging
                # module doesn't support passing in extra context.
                # For this handler, the only extra data we need is the
                # request, and that's in the top stack frame.
                request = record.exc_info[2].tb_frame.f_locals['request']
            else:
                request = record.request

            subject = '%s (%s IP): %s' % (
                record.levelname,
                (request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS and 'internal' or 'EXTERNAL'),
                record.msg
            )
            request_repr = repr(request)
        except:
            subject = 'Error: Unknown URL'
            request = None
            request_repr = "Request repr() unavailable"

        if record.exc_info:
            exc_info = record.exc_info
            stack_trace = '\n'.join(traceback.format_exception(*record.exc_info))
        else:
            exc_info = ()
            stack_trace = 'No stack trace available'

        message = "%s\n\n%s" % (stack_trace, request_repr)
        reporter = ExceptionReporter(request, is_email=True, *exc_info)
        mail.mail_admins(subject, message, fail_silently=True)
