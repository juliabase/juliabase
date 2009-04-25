class TransactionMiddleware(object):
    def process_request(self, request):
        request.refdb_rollback_actions = []

    def process_exception(self, request, exception):
        for action in reversed(request.refdb_rollback_actions):
            action.execute()
