#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2009 Torsten Bronger <bronger@physik.rwth-aachen.de>
#
# This file is part of Django-RefDB.
#
#     Django-RefDB is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public
#     License as published by the Free Software Foundation, either
#     version 3 of the License, or (at your option) any later
#     version.
#
#     Django-RefDB is distributed in the hope that it will be
#     useful, but WITHOUT ANY WARRANTY; without even the implied
#     warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#     PURPOSE.  See the GNU Affero General Public License for more
#     details.
#
#     You should have received a copy of the GNU Affero General
#     Public License along with Django-RefDB.  If not, see
#     <http://www.gnu.org/licenses/>.


u"""All middleware classes of Django-RefDB.
"""

import hashlib, datetime
from chantal_common import utils as chantal_utils
from ..views import utils


class ConditionalViewMiddleware(object):
    u"""Middleware class for setting the ETag properly.  If there is a success
    report at the top of the page (e.g. “Reference Miller2003 was successfully
    edited”), the ETag must be altered because otherwise, a reload or
    re-visiting of the page doesn't take the success report away.  The page
    simply is not exactly the same as it was without the success report.

    This is done here.  Eventually, this can also be achieved with Ajax.
    """

    def process_request(self, request):
        u"""Saves information about whether there is a success report on the
        page in the request object for later use in `process_response`.

        :Parameters:
          - `request`: the current HTTP request object

        :type request: ``HttpRequest``
        """
        request.alternate_etag = "success_report" in request.session or "db_access_time_in_ms" in request.session

    def process_response(self, request, response):
        u"""Alters the ETag if there was a success report on the page.  This
        does the actual work of this middleware.

        A good question is where to put this middleware.  It's probably best to
        make it outer than Django's CommonMiddleware so that ETags that
        CommonMiddleware produces can be altered here.  But actually it doesn't
        matter.  It's only important to generate an ETag which is unique in
        presence of a success report, and since the current timestamp is used,
        it will.

        :Parameters:
          - `request`: the current HTTP request object
          - `response`: the current HTTP response object

        :type request: ``HttpRequest``
        :type response: ``HttpResponse``

        :Return:
          the response object

        :rtype: ``HttpResponse``
        """
        if getattr(request, "alternate_etag", False):
            etag = hashlib.sha1()
            etag.update(response.get("ETag", ""))
            etag.update(repr(datetime.datetime.now()))
            response["ETag"] = etag.hexdigest()
        return response


class TransactionMiddleware(object):
    u"""Middleware class for pseudo-transactions for RefDB operations.  The
    main part of this feature can be found in the `refdb.utils` module.
    """
    
    def process_request(self, request):
        u"""Initiates the transaction by adding a new attribute called
        ``refdb_rollback_actions`` to the request instance.  It holds a list of
        the `refdb.utils.RefDBRollbacky` objects.

        :Parameters:
          - `request`: the current HTTP request object

        :type request: ``HttpRequest``
        """
        request.refdb_rollback_actions = []

    def process_exception(self, request, exception):
        u"""Walks through the list of accumulated rollback objects and executes
        them.

        :Parameters:
          - `request`: the current HTTP request object
          - `exception`: the exception that was raised and broke the request

        :type request: ``HttpRequest``
        :type exception: ``BaseException``
        """
        for action in reversed(request.refdb_rollback_actions):
            action.execute()


class RedirectMiddleware(object):
    u"""Middleware for catching redirect exceptions raised in the
    embed_common_data functions for the main menu and the bulk view.
    """
    def process_exception(self, request, exception):
        if isinstance(exception, utils.RedirectException):
            return chantal_utils.HttpResponseSeeOther(exception.redirect_to)
