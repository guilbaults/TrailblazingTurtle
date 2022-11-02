import functools
from django.http import HttpResponseForbidden
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
from ccldap.models import LdapAllocation, LdapUser
from ccldap.common import cc_storage_allocations, cc_compute_allocations_by_user, cc_compute_allocations_by_account
import yaml
from django.conf import settings
import os


# How many points in the X axis of the graphs
RESOLUTION = 500


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

        try:
            LdapAllocation.objects.filter(
                name=alloc_name,
                members=request.user.get_username(),
                status='active').get()
        except LdapAllocation.DoesNotExist:
            # This user is not in the allocation
            return HttpResponseForbidden()
        return func(request, *args, **kwargs)
    return wrapper


def openstackproject_or_staff(func):
    """Decorator to allow access if its the user is inside the project allocation or a staff member"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            # TODO search in LDAP
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
    return cc_compute_allocations_by_user(username)


def compute_allocations_by_account(account):
    """
    return the compute allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - cpu: the number of cpu allocated to the user (optional)
    - gpu: the number of gpu allocated to the user (optional)
    """
    return cc_compute_allocations_by_account(account)


def compute_allocations_by_slurm_account(account):
    """
    takes a slurm account name and return the number of cpu or gpu allocated to that account
    """
    account_name = account.rstrip('_gpu').rstrip('_cpu')
    allocs = compute_allocations_by_account(account_name)
    for alloc in allocs:
        if alloc['name'] == account:
            return alloc
    else:
        return None


def storage_allocations(username):
    """
    return the storage allocations for a user as a list of dictionaries with the following keys:
    - name: the name of the allocation
    - type: the type of the allocation (home, scratch, project or nearline as an example)
    - quota_bytes: the size of the allocation in bytes
    - quota_inodes: the inodes quota of the allocation
    """
    return cc_storage_allocations(username)


def cloud_projects_by_user(username):
    """
    Takes a username and returns a list of projects name that the user is a member of
    """
    # open the yaml file with the allocations
    with open(settings.CLOUD_ALLOCATIONS_FILE, 'r') as f:
        data = yaml.safe_load(f)
    # get the list of projects
    returned_projects = []
    projects = data['projects']
    for key in projects.keys():
        if username in projects[key]['members']:
            returned_projects.append(key)

    return returned_projects


def username_to_uid(username):
    """return the uid of a username"""
    return LdapUser.objects.filter(username=username).get().uid


def uid_to_username(uid):
    """return the username of a uid"""
    return LdapUser.objects.filter(uid=uid).get().username


def request_to_username(request):
    """return the username of a request"""
    return request.user.username.split('@')[0]


def query_time(request, exporter_name=None):
    delta = int(request.GET.get('delta', 0))

    if delta > 3600 * 24 * 7 * 30 * 6:
        # more than 6 months
        delta = 3600 * 24 * 7 * 30 * 6

    start = datetime.now() - timedelta(seconds=delta)

    if exporter_name in settings.EXPORTER_SAMPLING_RATE:
        step = max(int(delta / RESOLUTION), settings.EXPORTER_SAMPLING_RATE[exporter_name]) * 2
    else:
        step = max(int(delta / RESOLUTION), 30) * 2

    return (start, step)


def get_step(start, end=None):
    if end is None:
        end = datetime.now()
    if start is None:
        start = datetime.now()
    delta = end - start

    if delta.days > 6 * 30:
        # more than 6 months
        return 3600 * 24
    else:
        return int(delta.total_seconds() / RESOLUTION)


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

    def rate(self, exporter_name):
        # return twice the sampling rate of the exporter in seconds
        return int(settings.EXPORTER_SAMPLING_RATE[exporter_name]) * 2


# Override the function here with the one in local.py if file exist
if os.path.isfile(os.path.join(os.path.dirname(__file__), 'local.py')):
    from .local import *  # noqa
