from django.shortcuts import render, redirect
from userportal.common import user_or_staff, Prometheus, username_to_uid
from userportal.common import storage_allocations_project  # , storage_allocations_nearline
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from slurm.models import JobTable
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime, timedelta

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))


def get_quota_prometheus_request(quota_name, quota_type, inodes_bytes='inodes'):
    if inodes_bytes == 'inodes':
        return "lfs_quota_inodes{{path='{}', {}='{}', {} }}".format(
            settings.QUOTA_TYPES[quota_type][0],
            settings.QUOTA_TYPES[quota_type][1],
            quota_name,
            prom.get_filter())
    else:
        return "lfs_quota_kbytes{{path='{}', {}='{}', {} }} * 1024".format(
            settings.QUOTA_TYPES[quota_type][0],
            settings.QUOTA_TYPES[quota_type][1],
            quota_name,
            prom.get_filter())


def get_quota_prometheus(quota_name, quota_type, inodes_bytes='inodes'):
    try:
        query_quota = get_quota_prometheus_request(quota_name, quota_type, inodes_bytes)
        stats_quota = prom.query_last(query_quota)
        return int(stats_quota[0]['value'][1])
    except IndexError:
        return None


def get_quota_scratch(username):
    return {
        'inodes_quota': 10000000,
        'bytes_quota': 20 * 1024 * 1024 * 1024 * 1024,
        'inodes': get_quota_prometheus(username, 'scratch', 'inodes'),
        'bytes': get_quota_prometheus(username, 'scratch', 'bytes'),
    }


def get_quota_home(username):
    return {
        'inodes_quota': 500000,
        'bytes_quota': 50 * 1024 * 1024 * 1024,
        'inodes': get_quota_prometheus(username, 'home', 'inodes'),
        'bytes': get_quota_prometheus(username, 'home', 'bytes'),
    }


def get_quota_projects(username):
    context = {}
    alloc_projects = storage_allocations_project(username)
    # alloc_nearlines = storage_allocations_nearline(username)
    for project in alloc_projects:
        project['inodes'] = get_quota_prometheus(project['name'], 'project', 'inodes')
        project['bytes'] = get_quota_prometheus(project['name'], 'project', 'bytes')
    context['alloc_projects'] = alloc_projects
    # context['alloc_nearlines'] = alloc_nearlines
    return context


def get_allocated_quota(username, fs):
    if fs == 'scratch':
        return get_quota_scratch(username)
    elif fs == 'home':
        return get_quota_home(username)
    elif fs == 'project':
        return get_quota_projects(username)
    else:
        return None


@login_required
@user_or_staff
def user(request, username):
    uid = username_to_uid(username)
    context = {'username': username}

    if 'lfs_quota' in settings.EXPORTER_INSTALLED:
        context['scratch'] = get_quota_scratch(username)
        context['home'] = get_quota_home(username)
        project = get_quota_projects(username)
        context['alloc_projects'] = project['alloc_projects']
        # context['alloc_nearlines'] = project['alloc_nearlines']

    if 'jobstats' in settings.INSTALLED_APPS:
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


@login_required
@user_or_staff
def graph_inodes(request, username, fs):
    project_name = request.GET.get('project_name')
    if project_name is not None:
        query = get_quota_prometheus_request(project_name, fs, 'inodes')
        quota = get_allocated_quota(username, fs)
        # got all the quotas for this user, now we need to filter by project
        for project in quota['alloc_projects']:
            if project['name'] == project_name:
                quota = project
    else:
        query = get_quota_prometheus_request(username, fs, 'inodes')
        quota = get_allocated_quota(username, fs)

    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(days=90), datetime.now(), step="6h")

    data = {'lines': []}
    for line in stats:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Used inodes'),
        })

    data['layout'] = {
        'yaxis': {
            'range': [0, max(quota['inodes_quota'], max(line['y']))],
        },
        'showlegend': False,
        'margin': {
            'l': 70,
            'r': 10,
            'b': 50,
            't': 10,
            'pad': 0
        },
        'height': 300,
        'width': 300,
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_bytes(request, username, fs):
    project_name = request.GET.get('project_name')
    if project_name is not None:
        query = get_quota_prometheus_request(project_name, fs, 'bytes')
        quota = get_allocated_quota(username, fs)
        # got all the quotas for this user, now we need to filter by project
        for project in quota['alloc_projects']:
            if project['name'] == project_name:
                quota = project
        max_scale = quota['project_storage_bytes']  # somehow this is not the same key with project or user
    else:
        query = get_quota_prometheus_request(username, fs, 'bytes')
        quota = get_allocated_quota(username, fs)
        max_scale = quota['bytes_quota']

    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(days=180), datetime.now(), step="6h")

    data = {'lines': []}
    for line in stats:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Used bytes'),
        })

    data['layout'] = {
        'yaxis': {
            'range': [0, max(max_scale, max(line['y']))],
            'ticksuffix': 'B',
            'tickformat': '~s',
        },
        'showlegend': False,
        'margin': {
            'l': 70,
            'r': 10,
            'b': 50,
            't': 10,
            'pad': 0
        },
        'height': 300,
        'width': 300,
    }

    return JsonResponse(data)
