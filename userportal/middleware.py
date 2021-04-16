class ControlledUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        if 'REMOTE_USER' in request.META:
            # Behind shib
            if request.META['affiliation'] == 'staff@computecanada.ca':
                request.META['is_staff'] = True
            else:
                request.META['is_staff'] = False
            request.META['username'] = request.META['REMOTE_USER'].split('@')[0]
        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response
