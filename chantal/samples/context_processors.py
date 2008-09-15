#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Additional context processors for Chantal.  There functions must be added
to `settings.TEMPLATE_CONTEXT_PROCESSORS`.  They add further data to the
dictionary passed to the templates.
"""

def parse_session_data(request):
    u"""Injects some session data into the template context.  At the same time,
    it removes them from the session data so that the next view has to re-set
    them.  Obviously, this is meant to things that are displyed only once: the
    last DB access time, a possible success report in green colour à la “sample
    x was added sucessfully” and the help link on the top (see the
    `samples.views.utils.help_link` decorator).
    
    :Parameters:
      - `request`: the current HTTP Request object

    :type request: ``HttpRequest``

    :Returns:
      the (additional) context dictionary

    :rtype: dict mapping str to session data
    """
    result = {}
    for key in ["db_access_time_in_ms", "success_report", "success_report_meta", "help_link"]:
        if key in request.session:
            result[key] = request.session[key]
            del request.session[key]
    return result
