import functools
from django.http import HttpResponseNotFound
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
#from ccldap.models import LdapAllocation, LdapUser
#from ccldap.common import convert_ldap_to_allocation, storage_allocations_project, storage_allocations_nearline
from django.conf import settings

# for example purposes, use local uid resolver instead of ldap
import pwd

def user_or_staff(func):
    """Decorator to allow access only to staff members or to the user"""
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
    """Decorator to allow access if its the user is inside the project allocation or a staff member"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        alloc_name = kwargs['account'].split('_')[0]
        if request.META['is_staff']:
            return func(request, *args, **kwargs)
        else:
            # IMPLEMENTATION search in LDAP or other sources to check if the user is in the allocation
            return HttpResponseNotFound()
        #try:
        #    LdapAllocation.objects.filter(
        #        name=alloc_name,
        #        members=request.META['username'],
        #        status='active').get()
        #except LdapAllocation.DoesNotExist:
        #    # This user is not in the allocation
        #    return HttpResponseNotFound()
        #return func(request, *args, **kwargs)
    return wrapper


def openstackproject_or_staff(func):
    """Decorator to allow access if its the user is inside the project allocation or a staff member"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.META['is_staff']:
            return func(request, *args, **kwargs)
        else:
            # IMPLEMENTATION search in LDAP or other sources to check if the user is in the allocation
            return HttpResponseNotFound()
        return func(request, *args, **kwargs)
    return wrapper


def staff(func):
    """Decorator to allow access only to staff members"""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.META['is_staff']:
            return func(request, *args, **kwargs)
        else:
            return HttpResponseNotFound()
    return wrapper


def compute_allocations_by_user(username):
    allocations = LdapAllocation.objects.filter(members=username, status='active').all()
    return convert_ldap_to_allocation(allocations)


def compute_allocation_by_account(account):
    allocations = LdapAllocation.objects.filter(name=account, status='active').all()
    return convert_ldap_to_allocation(allocations)


def compute_default_allocation_by_user(username):
    """return the default allocations account names for a user"""
    # IMPLEMENTATION search in LDAP or other sources to check if the user is in the allocation
    return []
    #allocs = []
    #for alloc in LdapAllocation.objects.filter(members=username, status='active').all():
    #    if alloc.name.startswith('def-'):
    #        allocs.append(alloc.name)
    #return allocs


def compute_allocations_by_slurm_account(account):
    """takes a slurm account name and return the number of cpu or gpu allocated to that account"""
    account_name = account.rstrip('_gpu').rstrip('_cpu')
    allocations = compute_allocation_by_account(account_name)
    if account.endswith('_gpu'):
        for alloc in allocations:
            if 'gpu' in alloc:
                return alloc['gpu']
    else:
        for alloc in allocations:
            if 'cpu' in alloc:
                return alloc['cpu']
    return None


def storage_project_allocations_by_user(username):
    """return the storage allocation for a user"""
    return storage_allocations_project(username)


def storage_nearline_allocations_by_user(username):
    """return the nearline allocation for a user"""
    return storage_allocations_nearline(username)


def cloud_projects_by_user(username):
    """return the cloud allocation for a user"""
    # IMPLEMENTATION search in LDAP or other sources to get the allocations for the user
    return []
    # open the yaml file with the allocations
    #with open(settings.CLOUD_ALLOCATIONS_FILE, 'r') as f:
    #    data = yaml.safe_load(f)
    # get the list of projects
    #returned_projects = []
    #projects = data['projects']
    #for key in projects.keys():
    #    if username in projects[key]['members']:
    #        returned_projects.append(key)

    #return returned_projects


def username_to_uid(username):
    """return the uid of a username"""
    # IMPLEMENTATION search in LDAP, use local resolver as an example
    #return 3015160
    return int(pwd.getpwnam(username).pw_uid)
    #return LdapUser.objects.filter(username=username).get().uid


def uid_to_username(uid):
    """return the username of a uid"""
    # IMPLEMENTATION search in LDAP, use local resolver as an example
    #return "sigui4"
    return pwd.getpwuid(uid).pw_name
    #return LdapUser.objects.filter(uid=uid).get().username


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
        step = '1m'
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
