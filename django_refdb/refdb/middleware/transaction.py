#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Middleware for pseudo-transactions for RefDB operations.  The main part of
the code can be found in the `refdb.utils` module.
"""

class TransactionMiddleware(object):
    u"""Middleware class for pseudo-transactions for RefDB operations.
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
