from django.core.exceptions import PermissionDenied


class ControlledUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        if 'REMOTE_USER' in request.META:
            # Behind shib
            if 'staff@computecanada.ca' in request.META['affiliation'] \
                    or 'staff@alliancecan.ca' in request.META['affiliation']:
                request.META['is_staff'] = True
            else:
                request.META['is_staff'] = False
            remote_user = request.META['REMOTE_USER'].split('@')
            if remote_user[1] not in ['computecanada.ca', 'alliancecan.ca']:
                # Not a user from cc
                raise PermissionDenied
            request.META['username'] = remote_user[0]
        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response
