import functools
from django.http import HttpResponseNotFound


def user_or_staff(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.username.split('@')[0] == kwargs['username']:
            # own info
            return func(request, *args, **kwargs)
        elif request.META['affiliation'] == 'staff@computecanada.ca':
            # is staff
            return func(request, *args, **kwargs)
        else:
            return HttpResponseNotFound()
    return wrapper
