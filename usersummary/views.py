from django.shortcuts import render, redirect
from ccldap.models import LdapUser
from userportal.common import user_or_staff
from django.contrib.auth.decorators import login_required
from slurm.models import JobTable
from ccldap.common import storage_allocations
from userportal.common import Prometheus
from django.conf import settings

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))


def get_quota_prometheus(quota_name, quota_type, inodes_bytes='inodes'):
    if inodes_bytes == 'inodes':
        metric_name = 'lfs_quota_inodes'
    else:
        metric_name = 'lfs_quota_kbytes'

    try:
        query_quota = "{}{{path='{}', {}='{}', {} }}".format(
            metric_name,
            settings.QUOTA_TYPES[quota_type][0],
            settings.QUOTA_TYPES[quota_type][1],
            quota_name,
            prom.get_filter())
        stats_quota = prom.query_last(query_quota)
        if inodes_bytes == 'inodes':
            return int(stats_quota[0]['value'][1])
        else:
            return int(stats_quota[0]['value'][1]) * 1024  # return it in bytes
    except IndexError:
        return None


@login_required
@user_or_staff
def user(request, username):
    uid = LdapUser.objects.filter(username=username).get().uid
    context = {'username': username}

    context['scratch'] = {
        'inodes_quota': 10000000,
        'bytes_quota': 20 * 1024 * 1024 * 1024 * 1024,
        'inodes': get_quota_prometheus(username, 'scratch', 'inodes'),
        'bytes': get_quota_prometheus(username, 'scratch', 'bytes'),
    }
    context['home'] = {
        'inodes_quota': 500000,
        'bytes_quota': 50 * 1024 * 1024 * 1024,
        'inodes': get_quota_prometheus(username, 'home', 'inodes'),
        'bytes': get_quota_prometheus(username, 'home', 'bytes'),
    }

    alloc_projects, alloc_nearlines = storage_allocations(username)
    for project in alloc_projects:
        project['inodes'] = get_quota_prometheus(project['name'], 'project', 'inodes')
        project['bytes'] = get_quota_prometheus(project['name'], 'project', 'bytes')
    context['alloc_projects'] = alloc_projects
    context['alloc_nearlines'] = alloc_nearlines

    pending_jobs = JobTable.objects.filter(
        id_user=uid, state=0).order_by('-time_submit')

    job_start = JobTable.objects.filter(
        id_user=uid).order_by('-time_submit')
    job_end = JobTable.objects.filter(
        id_user=uid).order_by('-time_submit')

    context['jobs'] = (pending_jobs | job_start | job_end)[:10]

    running_jobs = JobTable.objects.filter(id_user=uid, state=1).all()
    context['total_cores'] = 0
    context['total_mem'] = 0
    context['total_gpus'] = 0
    for job in running_jobs:
        info = job.parse_tres_req()
        context['total_cores'] += info['total_cores']
        context['total_mem'] += (info['total_mem'] * 1024 * 1024)
        context['total_gpus'] += job.gpu_count()

    return render(request, 'usersummary/user.html', context)
