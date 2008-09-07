#!/usr/bin/env python
# -*- coding: utf-8 -*-

def parse_session_data(request):
    result = {}
    for key in ["db_access_time_in_ms", "success_report", "help_link"]:
        if key in request.session:
            result[key] = request.session[key]
            del request.session[key]
    return result
