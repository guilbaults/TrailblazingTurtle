from django.shortcuts import render, redirect
from userportal.common import user_or_staff, Prometheus, username_to_uid, parse_start_end
from userportal.common import storage_allocations
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from slurm.models import JobTable
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from datetime import timedelta

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))


def get_quota_prometheus_request(resource_type, resource_name, inodes_bytes='inodes'):
    if inodes_bytes == 'inodes':
        return "lfs_quota_inodes{{path='{}', {}='{}', {} }}".format(
            settings.QUOTA_TYPES[resource_type][0],
            settings.QUOTA_TYPES[resource_type][1],
            resource_name,
            prom.get_filter())
    else:
        return "lfs_quota_kbytes{{path='{}', {}='{}', {} }} * 1024".format(
            settings.QUOTA_TYPES[resource_type][0],
            settings.QUOTA_TYPES[resource_type][1],
            resource_name,
            prom.get_filter())


def get_quota_prometheus(resource_type, resource_name, inodes_bytes='inodes'):
    try:
        query_quota = get_quota_prometheus_request(resource_name, resource_type, inodes_bytes)
        stats_quota = prom.query_last(query_quota)
        return int(stats_quota[0]['value'][1])
    except IndexError:
        return None


@login_required
@user_or_staff
def user(request, username):
    uid = username_to_uid(username)
    context = {'username': username}

    if 'lfs_quota' in settings.EXPORTER_INSTALLED:
        allocs = storage_allocations(username)
        for alloc in allocs:
            alloc['inodes'] = get_quota_prometheus(alloc['name'], alloc['type'], 'inodes')
            alloc['bytes'] = get_quota_prometheus(alloc['name'], alloc['type'], 'bytes')
        context['allocs'] = allocs

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
@parse_start_end(timedelta_start=timedelta(days=90))
def graph_inodes(request, username, resource_type, resource_name):
    allocs = storage_allocations(username)
    for alloc in allocs:
        if alloc['name'] == resource_name and alloc['type'] == resource_type:
            quota = alloc['quota_inodes']
            break
    else:
        return HttpResponseForbidden

    query = get_quota_prometheus_request(resource_type, resource_name, 'inodes')
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    if len(stats) > 0:
        for line in stats:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': _('Used inodes'),
            })
    else:
        return JsonResponse({'data': data})

    layout = {
        'yaxis': {
            'range': [0, max(quota, max(line['y']))],
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

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@user_or_staff
@parse_start_end(timedelta_start=timedelta(days=90))
def graph_bytes(request, username, resource_type, resource_name):
    allocs = storage_allocations(username)
    for alloc in allocs:
        if alloc['name'] == resource_name and alloc['type'] == resource_type:
            quota = alloc['quota_bytes']
            break
    else:
        return HttpResponseForbidden

    query = get_quota_prometheus_request(resource_type, resource_name, 'bytes')
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    if len(stats) > 0:
        for line in stats:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': _('Used bytes'),
            })
    else:
        return JsonResponse({'data': data})

    layout = {
        'yaxis': {
            'range': [0, max(quota, max(line['y']))],
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

    return JsonResponse({'data': data, 'layout': layout})
