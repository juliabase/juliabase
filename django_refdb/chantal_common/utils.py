#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.  Django-RefDB is published under the MIT
# license.  A copy of this licence is shipped with Django-RefDB in the file
# LICENSE.


from __future__ import absolute_import


class HttpResponseUnauthorized(django.http.HttpResponse):
    u"""The response sent back in case of a permission error.  This is another
    missing response class in Django.  I have no clue why they leave out such
    trivial code.
    """
    status_code = 401
