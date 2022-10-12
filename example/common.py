import functools
from django.http import HttpResponseForbidden
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
from django.conf import settings
import pwd


"""
This example is using MagicCastle and FreeIPA
https://github.com/ComputeCanada/magic_castle/
"""


def user_or_staff(func):
    """Decorator to allow access only to staff members or to the user"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.get_username() == kwargs['username']:
            # own info
            return func(request, *args, **kwargs)
        elif request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()
    return wrapper


def account_or_staff(func):
    """Decorator to allow access if its the user is inside the project allocation or a staff member"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        alloc_name = kwargs['account'].split('_')[0]
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            # IMPLEMENTATION search in LDAP or other sources to check if the user is in the allocation
            return HttpResponseForbidden()
    return wrapper


def openstackproject_or_staff(func):
    """Decorator to allow access if its the user is inside the project allocation or a staff member"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            # IMPLEMENTATION search in LDAP or other sources to check if the user is in the allocation
            return HttpResponseForbidden()
        return func(request, *args, **kwargs)
    return wrapper


def staff(func):
    """Decorator to allow access only to staff members"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()
    return wrapper


def compute_allocations_by_user(username):
    """
    return the compute allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - cpu: the number of cpu allocated to the user (optional)
    - gpu: the number of gpu allocated to the user (optional)
    """
    return [{'name': 'def-sponsor00', 'cpu': 1, }]


def compute_allocations_by_account(account):
    """
    return the compute allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - cpu: the number of cpu allocated to the user (optional)
    - gpu: the number of gpu allocated to the user (optional)
    """
    return [{'name': 'def-sponsor00', 'cpu': 1, }]


def compute_allocations_by_slurm_account(account):
    """
    takes a slurm account name and return the number of cpu or gpu allocated to that account
    Returns:
        int: the number of cpu or gpu allocated to that account
    """
    return 1


def storage_allocations(username):
    """
    return the storage allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - type: the type of the allocation (home, scratch, project or nearline as an example)
    - quota_bytes: the size of the allocation in bytes
    - quota_inodes: the inodes quota of the allocation
    """
    return [{'name': 'def-sponsor00', 'type': 'home', 'quota_bytes': 1000000000000, 'quota_inodes': 1000000}]


def cloud_projects_by_user(username):
    """return the cloud allocation for a user"""
    # IMPLEMENTATION search in LDAP or other sources to get the allocations for the user
    return []


def username_to_uid(username):
    """return the uid of a username"""
    return int(pwd.getpwnam(username).pw_uid)


def uid_to_username(uid):
    """return the username of a uid"""
    return pwd.getpwuid(uid).pw_name


def request_to_username(request):
    """return the username of a request"""
    return request.user.username.split('@')[0]


def query_time(request):
    delta = request.GET.get('delta', '1h')
    if delta == '1m':
        start = datetime.now() - timedelta(weeks=4)
        step = '3h'
    elif delta == '1w':
        start = datetime.now() - timedelta(weeks=1)
        step = '30m'
    elif delta == '1d':
        start = datetime.now() - timedelta(days=1)
        step = '5m'
    else:
        # default to 1 hour
        start = datetime.now() - timedelta(hours=1)
        step = '30s'
    return (start, step)


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
