import functools
from django.http import HttpResponseNotFound
from prometheus_api_client import PrometheusConnect
from datetime import datetime
from ccldap.models import LdapAllocation


def user_or_staff(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.META['username'] == kwargs['username']:
            # own info
            return func(request, *args, **kwargs)
        elif request.META['is_staff']:
            return func(request, *args, **kwargs)
        else:
            return HttpResponseNotFound()
    return wrapper


def account_or_staff(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        alloc_name = kwargs['account'].split('_')[0]
        if request.META['is_staff']:
            return func(request, *args, **kwargs)

        try:
            LdapAllocation.objects.filter(
                name=alloc_name,
                members=request.META['username'],
                status='active').get()
        except LdapAllocation.DoesNotExist:
            # This user is not in the allocation
            return HttpResponseNotFound()
        return func(request, *args, **kwargs)
    return wrapper


def openstackproject_or_staff(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.META['is_staff']:
            return func(request, *args, **kwargs)
        else:
            # TODO search in LDAP
            return HttpResponseNotFound()
        return func(request, *args, **kwargs)
    return wrapper


def staff(func):
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.META['is_staff']:
            return func(request, *args, **kwargs)
        else:
            return HttpResponseNotFound()
    return wrapper


class Prometheus:
    def __init__(self, config):
        self.prom = PrometheusConnect(
            url=config['url'],
            headers=config['headers'])
        self.filter = config['filter']

    def get_filter(self):
        return self.filter

    def query_prometheus(self, query, duration, end=None, step='3m'):
        values = self.query_prometheus_multiple(query, duration, end, step)
        if len(values) == 0:
            raise ValueError
        return (values[0]['x'], values[0]['y'])

    def query_prometheus_multiple(self, query, start, end=None, step='3m'):
        if end is None:
            end = datetime.now()
        q = self.prom.custom_query_range(
            query=query,
            start_time=start,
            end_time=end,
            step=step,
        )
        return_list = []
        for line in q:
            return_list.append({
                'metric': line['metric'],
                'x': [datetime.fromtimestamp(x[0]) for x in line['values']],
                'y': [float(x[1]) for x in line['values']]
            })
        return return_list

    def query_last(self, query):
        q = self.prom.custom_query(query)
        return q
