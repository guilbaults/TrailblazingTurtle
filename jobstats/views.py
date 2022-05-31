from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound, JsonResponse
from slurm.models import JobTable
from userportal.common import user_or_staff, username_to_uid, Prometheus, request_to_username
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from rest_framework import viewsets
from rest_framework import permissions
from jobstats.models import JobScript
from jobstats.serializers import JobScriptSerializer
import statistics
from django.core.paginator import Paginator

GPU_MEMORY = {'Tesla V100-SXM2-16GB': 16, 'NVIDIA A100-SXM4-40GB': 40}
GPU_FULL_POWER = {'Tesla V100-SXM2-16GB': 300, 'NVIDIA A100-SXM4-40GB': 400}
GPU_IDLE_POWER = {'Tesla V100-SXM2-16GB': 55, 'NVIDIA A100-SXM4-40GB': 55}
GPU_SHORT_NAME = {'NVIDIA A100-SXM4-40GB': 'A100', 'Tesla V100-SXM2-16GB': 'V100'}

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    return redirect('{}/'.format(request_to_username(request)))


@login_required
@user_or_staff
def user(request, username):
    uid = username_to_uid(username)
    context = {'username': username}
    jobs = JobTable.objects.filter(id_user=uid).order_by('-time_submit')
    paginator = Paginator(jobs, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context['jobs'] = page_obj

    running_jobs = JobTable.objects.filter(id_user=uid, state=1).all()
    context['total_cores'] = 0
    context['total_mem'] = 0
    context['total_gpus'] = 0
    for job in running_jobs:
        info = job.parse_tres_req()
        context['total_cores'] += info['total_cores']
        context['total_mem'] += (info['total_mem'] * 1024 * 1024)
        context['total_gpus'] += job.gpu_count()

    now = datetime.now()
    delta = timedelta(hours=1)
    try:
        query_cpu = 'sum(rate(slurm_job_core_usage_total{{user="{}", {}}}[2m]) / 1000000000)'.format(username, prom.get_filter())
        stats_cpu = prom.query_prometheus(query_cpu, now - delta, now)
        context['cpu_used'] = statistics.mean(stats_cpu[1])
    except ValueError:
        context['cpu_used'] = 'N/A'

    try:
        query_mem = 'sum(slurm_job_memory_max{{user="{}", {}}})'.format(username, prom.get_filter())
        stats_mem = prom.query_prometheus(query_mem, now - delta, now)
        context['mem_used'] = max(stats_mem[1])
    except ValueError:
        context['mem_used'] = 'N/A'

    try:
        query_gpu = 'sum(slurm_job_utilization_gpu{{user="{}", {}}})/100'.format(username, prom.get_filter())
        stats_gpu = prom.query_prometheus(query_gpu, now - delta, now)
        context['gpu_used'] = max(stats_gpu[1])
    except ValueError:
        context['gpu_used'] = 'N/A'

    return render(request, 'jobstats/user.html', context)


@login_required
@user_or_staff
def job(request, username, job_id):
    uid = username_to_uid(username)
    context = {'job_id': job_id}
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('<h1>Job not found</h1>')
    context['job'] = job
    context['tres_req'] = job.parse_tres_req()
    context['total_mem'] = context['tres_req']['total_mem'] * 1024 * 1024

    try:
        context['job_script'] = JobScript.objects.filter(id_job=job_id).get()
    except JobScript.DoesNotExist:
        context['job_script'] = None

    if 'slurm_exporter' in settings.EXPORTER_INSTALLED:
        try:
            query_priority = 'slurm_account_levelfs{{account="{account}", {filter}}}'.format(
                account=job.account,
                filter=prom.get_filter()
            )
            if job.time_start_dt() is not None:
                # If the job has started, use the start time.
                stats_priority = prom.query_prometheus(query_priority, job.time_start_dt(), job.time_start_dt() + timedelta(minutes=15))
                context['priority'] = stats_priority[1][0]
            else:
                # Otherwise, use the current time.
                stats_priority = prom.query_last(query_priority)
                context['priority'] = stats_priority[0]['value'][1]
        except ValueError:
            context['priority'] = 'N/A'

    if job.time_start_dt() is None:
        return render(request, 'jobstats/job.html', context)

    try:
        query_cpu = 'sum(rate(slurm_job_core_usage_total{{slurmjobid="{}", {}}}[2m]) / 1000000000)'.format(job_id, prom.get_filter())
        stats_cpu = prom.query_prometheus(query_cpu, job.time_start_dt(), job.time_end_dt())
        context['cpu_used'] = statistics.mean(stats_cpu[1])
    except ValueError:
        context['cpu_used'] = 'N/A'

    try:
        query_mem = 'sum(slurm_job_memory_max{{slurmjobid="{}", {}}})'.format(job_id, prom.get_filter())
        stats_mem = prom.query_prometheus(query_mem, job.time_start_dt(), job.time_end_dt())
        context['mem_used'] = max(stats_mem[1])
    except ValueError:
        context['mem_used'] = 'N/A'

    if job.gpu_count() > 0:
        try:
            query_gpu_util = 'sum(slurm_job_utilization_gpu{{slurmjobid="{}", {}}})'.format(job_id, prom.get_filter())
            stats_gpu_util = prom.query_prometheus(query_gpu_util, job.time_start_dt(), job.time_end_dt())
            context['gpu_used'] = statistics.mean(stats_gpu_util[1])
        except ValueError:
            context['gpu_used'] = 'N/A'

        try:
            query_gpu_mem = 'sum(slurm_job_memory_usage_gpu{{slurmjobid="{}", {}}})/(1024*1024*1024)'.format(job_id, prom.get_filter())
            stats_gpu_mem = prom.query_prometheus(query_gpu_mem, job.time_start_dt(), job.time_end_dt())
            context['gpu_mem'] = max(stats_gpu_mem[1]) / GPU_MEMORY[job.gpu_type()] * 100
        except ValueError:
            context['gpu_mem'] = 'N/A'

        try:
            query_gpu_power = 'sum(slurm_job_power_gpu{{slurmjobid="{}", {}}})/(1000)'.format(job_id, prom.get_filter())
            stats_gpu_power = prom.query_prometheus(query_gpu_power, job.time_start_dt(), job.time_end_dt())
            used_power = statistics.mean(stats_gpu_power[1]) - GPU_IDLE_POWER[job.gpu_type()]
            context['gpu_power'] = used_power / GPU_FULL_POWER[job.gpu_type()] * 100
        except ValueError:
            context['gpu_power'] = 'N/A'

    return render(request, 'jobstats/job.html', context)


@login_required
@user_or_staff
def graph_cpu(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    query = 'rate(slurm_job_core_usage_total{{slurmjobid="{}", {}}}[2m]) / 1000000000'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = {'lines': []}
    for line in stats:
        core_num = int(line['metric']['core'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} core {}'.format(compute_name, core_num)
        })

    data['layout'] = {
        'yaxis': {
            'range': [0, job.parse_tres_req()['total_cores']],
            'title': _('Cores'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_cpu_user(request, username):
    data = {'lines': []}
    try:
        query_used = 'sum(rate(slurm_job_core_usage_total{{user="{}", {}}}[1m])) / 1000000000'.format(username, prom.get_filter())
        stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
            'y': stats_used[1],
            'type': 'scatter',
            'name': _('Used')
        })

        query_alloc = 'sum(count(slurm_job_core_usage_total{{user="{}", {}}}))'.format(username, prom.get_filter())
        stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
            'y': stats_alloc[1],
            'type': 'scatter',
            'name': _('Allocated')
        })
    except ValueError:
        return JsonResponse(data)

    data['layout'] = {
        'yaxis': {
            'range': [0, max(stats_alloc[1])],
            'title': _('Cores'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_mem_user(request, username):
    data = {'lines': []}

    try:
        query_alloc = 'sum(slurm_job_memory_limit{{user="{}", {}}})/(1024*1024*1024)'.format(username, prom.get_filter())
        stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
            'y': stats_alloc[1],
            'type': 'scatter',
            'name': _('Allocated')
        })

        query_max = 'sum(slurm_job_memory_max{{user="{}", {}}})/(1024*1024*1024)'.format(username, prom.get_filter())
        stats_max = prom.query_prometheus(query_max, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_max[0])),
            'y': stats_max[1],
            'type': 'scatter',
            'name': _('Max used')
        })

        query_used = 'sum(slurm_job_memory_usage{{user="{}", {}}})/(1024*1024*1024)'.format(username, prom.get_filter())
        stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
            'y': stats_used[1],
            'type': 'scatter',
            'name': _('Used')
        })
    except ValueError:
        return JsonResponse(data)

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'range': [0, max(stats_alloc[1])],
            'title': _('Memory'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_mem(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    data = {'lines': []}

    stat_types = [
        ('slurm_job_memory_limit', _('Allocated')),
        ('slurm_job_memory_max', _('Max used')),
        ('slurm_job_memory_usage', _('Used')),
        ('slurm_job_memory_cache', _('Cache')),
        ('slurm_job_memory_rss', _('RSS')),
        ('slurm_job_memory_rss_huge', _('RSS Huge')),
        ('slurm_job_memory_mapped_file', _('Memory mapped file')),
        ('slurm_job_memory_active_file', _('Active file')),
        ('slurm_job_memory_inactive_file', _('Inactive file')),
        ('slurm_job_memory_unevictable', _('Unevictable')),
    ]

    for stat in stat_types:
        query = '{}{{slurmjobid="{}", {}}}/(1024*1024*1024)'.format(stat[0], job_id, prom.get_filter())
        stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())
        for line in stats:
            compute_name = line['metric']['instance'].split(':')[0]
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(stat[1], compute_name)
            })
        if stat[0] == 'slurm_job_memory_limit':
            maximum = max(max(map(lambda x: x['y'], stats)))

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'range': [0, maximum],
            'title': _('Memory'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_lustre_mdt(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    query = 'sum(rate(lustre_job_stats_total{{component=~"mdt",jobid=~"{}", {}}}[5m])) by (operation, fs) !=0'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = {'lines': []}
    for line in stats:
        operation = line['metric']['operation']
        fs = line['metric']['fs']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} {}'.format(operation, fs)
        })

    data['layout'] = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_lustre_mdt_user(request, username):
    query = 'sum(rate(lustre_job_stats_total{{component=~"mdt",user=~"{}", {}}}[5m])) by (operation, fs) !=0'.format(username, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), datetime.now())
    data = {'lines': []}
    for line in stats:
        operation = line['metric']['operation']
        fs = line['metric']['fs']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} {}'.format(operation, fs)
        })

    data['layout'] = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_lustre_ost(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    data = {'lines': []}
    for i in ['read', 'write']:
        query = '(sum(rate(lustre_job_{}_bytes_total{{component=~"ost",jobid=~"{}",target=~".*-OST.*", {}}}[5m])) by (fs)) / (1024*1024)'.format(i, job_id, prom.get_filter())
        stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

        for line in stats:
            fs = line['metric']['fs']
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(i, fs)
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' MiB/s',
            'title': _('Bandwidth'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_lustre_ost_user(request, username):
    data = {'lines': []}
    for i in ['read', 'write']:
        query = '(sum(rate(lustre_job_{}_bytes_total{{component=~"ost",user=~"{}",target=~".*-OST.*", {}}}[5m])) by (fs)) / (1024*1024)'.format(i, username, prom.get_filter())
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), datetime.now())

        for line in stats:
            fs = line['metric']['fs']
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(i, fs)
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' MiB/s',
            'title': _('Bandwidth'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_utilization(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_utilization_gpu{{slurmjobid="{}", {}}}'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' %',
            'range': [0, 100],
            'title': _('GPU Utilization'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_utilization_user(request, username):
    data = {'lines': []}

    query_alloc = 'count(slurm_job_utilization_gpu{{user="{}", {}}})'.format(username, prom.get_filter())
    stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
        'y': stats_alloc[1],
        'type': 'scatter',
        'name': _('Allocated')
    })

    query_used = 'sum(slurm_job_utilization_gpu{{user="{}", {}}})/100'.format(username, prom.get_filter())
    stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
        'y': stats_used[1],
        'type': 'scatter',
        'name': _('Used')
    })

    data['layout'] = {
        'yaxis': {
            'title': _('GPU Utilization'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_memory_utilization(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_utilization_gpu_memory{{slurmjobid="{}", {}}}'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' %',
            'range': [0, 100],
            'title': _('GPU Memory Utilization'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_memory(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_memory_usage_gpu{{slurmjobid="{}", {}}} /(1024*1024*1024)'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        gpu_type = line['metric']['gpu_type']
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' GiB',
            'range': [0, GPU_MEMORY[gpu_type]],
            'title': _('GPU Memory Usage'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_power(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_power_gpu{{slurmjobid="{}", {}}}/1000'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        gpu_type = line['metric']['gpu_type']
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })

    data['lines'].append({
        'x': x,
        'y': [GPU_IDLE_POWER[gpu_type] for x in y],
        'type': 'scatter',
        'name': '{} {}'.format(_('Idle power'), GPU_SHORT_NAME[gpu_type]),
    })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' W',
            'range': [0, GPU_FULL_POWER[gpu_type]],
            'title': _('GPU Power Usage'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_power_user(request, username):
    data = {'lines': []}

    query_alloc = 'count(slurm_job_power_gpu{{user="{}", {}}}) by (gpu_type)'.format(username, prom.get_filter())
    stats_alloc = prom.query_prometheus_multiple(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())
    for line in stats_alloc:
        gpu_type = line['metric']['gpu_type']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': [GPU_FULL_POWER[gpu_type] * z for z in y],
            'type': 'scatter',
            'name': '{} {}'.format(_('Allocated'), GPU_SHORT_NAME[gpu_type])
        })

        data['lines'].append({
            'x': x,
            'y': [GPU_IDLE_POWER[gpu_type] * z for z in y],
            'type': 'scatter',
            'name': '{} {}'.format(_('Idle power'), GPU_SHORT_NAME[gpu_type]),
        })

    query_used = 'sum(slurm_job_power_gpu{{user="{}", {}}}) by (gpu_type) / 1000'.format(username, prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, datetime.now() - timedelta(hours=6), datetime.now())
    for line in stats_used:
        gpu_type = line['metric']['gpu_type']
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': '{} {}'.format(_('Used'), GPU_SHORT_NAME[gpu_type])
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'W',
            'title': _('GPU Power Usage'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_pcie(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    data = {'lines': []}
    # Not sure if this scale is correct, the API report both bytes and kb/s
    query = 'slurm_job_pcie_gpu{{slurmjobid="{}", {}}}/(1024*1024)'.format(job_id, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        direction = line['metric']['direction']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} GPU{} {}'.format(compute_name, gpu_num, direction)
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' MB/s',
            'title': _('Bandwidth'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_infiniband_bdw(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')
    nodes = job.nodes()
    instances = '|'.join([s + ':9100' for s in nodes])

    data = {'lines': []}

    query_received = 'rate(node_infiniband_port_data_received_bytes_total{{instance=~"{}", {}}}[2m]) * 8 / (1000*1000*1000)'.format(instances, prom.get_filter())
    stats_received = prom.query_prometheus_multiple(query_received, job.time_start_dt(), job.time_end_dt())
    for line in stats_received:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Received {}'.format(compute_name)
        })

    query_transmitted = 'rate(node_infiniband_port_data_transmitted_bytes_total{{instance=~"{}", {}}}[2m]) * 8 /(1000*1000*1000)'.format(instances, prom.get_filter())
    stats_transmitted = prom.query_prometheus_multiple(query_transmitted, job.time_start_dt(), job.time_end_dt())
    for line in stats_transmitted:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Transmitted {}'.format(compute_name)
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' Gb/s',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_disk_iops(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')
    nodes = job.nodes()
    instances = '|'.join([s + ':9100' for s in nodes])

    data = {'lines': []}

    query_read = 'rate(node_disk_reads_completed_total{{instance=~"{}",device=~"nvme0n1|sda", {}}}[2m])'.format(instances, prom.get_filter())
    stats_read = prom.query_prometheus_multiple(query_read, job.time_start_dt(), job.time_end_dt())
    for line in stats_read:
        compute_name = "{} {}".format(
            line['metric']['instance'].split(':')[0],
            line['metric']['device'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Read {}'.format(compute_name)
        })

    query_write = 'rate(node_disk_writes_completed_total{{instance=~"{}",device=~"nvme0n1|sda", {}}}[2m])'.format(instances, prom.get_filter())
    stats_write = prom.query_prometheus_multiple(query_write, job.time_start_dt(), job.time_end_dt())
    for line in stats_write:
        compute_name = "{} {}".format(
            line['metric']['instance'].split(':')[0],
            line['metric']['device'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Write {}'.format(compute_name)
        })

    data['layout'] = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_disk_bdw(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')
    nodes = job.nodes()
    instances = '|'.join([s + ':9100' for s in nodes])

    data = {'lines': []}

    query_read = 'rate(node_disk_read_bytes_total{{instance=~"{}",device=~"nvme0n1|sda", {}}}[2m])'.format(instances, prom.get_filter())
    stats_read = prom.query_prometheus_multiple(query_read, job.time_start_dt(), job.time_end_dt())
    for line in stats_read:
        compute_name = "{} {}".format(
            line['metric']['instance'].split(':')[0],
            line['metric']['device'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Read {}'.format(compute_name)
        })

    query_write = 'rate(node_disk_written_bytes_total{{instance=~"{}",device=~"nvme0n1|sda", {}}}[2m])'.format(instances, prom.get_filter())
    stats_write = prom.query_prometheus_multiple(query_write, job.time_start_dt(), job.time_end_dt())
    for line in stats_write:
        compute_name = "{} {}".format(
            line['metric']['instance'].split(':')[0],
            line['metric']['device'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Write {}'.format(compute_name)
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'B/s',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_disk_used(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')
    nodes = job.nodes()
    instances = '|'.join([s + ':9100' for s in nodes])

    data = {'lines': []}

    query_disk = '(node_filesystem_size_bytes{{instance=~"{}",mountpoint="/localscratch", {}}} - node_filesystem_avail_bytes{{instance=~"{}",mountpoint="/localscratch", {}}})/(1000*1000*1000)'.format(
        instances, prom.get_filter(), instances, prom.get_filter())
    stats_disk = prom.query_prometheus_multiple(query_disk, job.time_start_dt(), job.time_end_dt())
    for line in stats_disk:
        compute_name = "{} {}".format(
            line['metric']['instance'].split(':')[0],
            line['metric']['device'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': compute_name
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' GB',
            'title': _('Disk used'),
        }
    }

    return JsonResponse(data)


def power(job):
    nodes = job.nodes()
    if job.gpu_count() > 0:
        # ( take the node power
        # - remove the power of all the GPUs in the compute)
        # * (multiply that by the ratio of GPUs used in that node)
        # + (add the power of the gpu allocated to the job)
        # results is not perfect when the node is shared between jobs
        query = '(label_replace(sum(redfish_chassis_power_average_consumed_watts{{instance=~"({nodes})-oob", {filter} }}) by (instance), "instance", "$1", "instance", "(.*)-oob") \
- label_replace((sum(nvidia_gpu_power_usage_milliwatts{{instance=~"({nodes}):9445", {filter}}} / 1000) by (instance)), "instance", "$1", "instance", "(.*):.*"))\
* ( label_replace(count(slurm_job_power_gpu{{slurmjobid="{jobid}", {filter}}} / 1000) by (instance),"instance", "$1", "instance", "(.*):.*") / label_replace((count(nvidia_gpu_power_usage_milliwatts{{instance=~"({nodes}):9445", {filter}}} / 1000) by (instance)), "instance", "$1", "instance", "(.*):.*") )\
+ ( label_replace(sum(slurm_job_power_gpu{{slurmjobid="{jobid}", {filter}}} / 1000) by (instance),"instance", "$1", "instance", "(.*):.*") )'.format(
            nodes='|'.join(nodes),
            filter=prom.get_filter(),
            jobid=job.id_job,
        )
    else:
        # ( take the node power)
        # * (the ratio of cpu cores allocated in that node)
        query = '(label_replace(sum(redfish_chassis_power_average_consumed_watts{{instance=~"({nodes})-oob", {filter} }}) by (instance), "instance", "$1", "instance", "(.*)-oob") ) \
            * ( label_replace(count(slurm_job_core_usage_total{{slurmjobid="{jobid}", {filter}}} / 1000) by (instance),"instance", "$1", "instance", "(.*):.*") / label_replace((count(node_cpu_seconds_total{{instance=~"({nodes}):9100", mode="idle", {filter}}} / 1000) by (instance)), "instance", "$1", "instance", "(.*):.*") )'.format(
            nodes='|'.join(nodes),
            filter=prom.get_filter(),
            jobid=job.id_job,
        )
    return prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())


@login_required
@user_or_staff
def graph_power(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    data = {'lines': []}
    for line in power(job):
        compute_name = "{}".format(line['metric']['instance'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        data['lines'].append({
            'x': x,
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': compute_name
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' W',
            'title': _('Power'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def value_cost(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')
    if job.used_time() is None:
        # Job has not been run yet
        return JsonResponse({})

    hours = job.used_time() / 3600  # compute the duration of the job

    response = {}
    if 'redfish_exporter' in settings.EXPORTER_INSTALLED:
        kwhs = []
        for line in power(job):
            # Instead of a proper integration, we just multiply the avg power by the time
            kw = (sum(line['y']) / len(line['y'])) / 1000  # compute the average power consumption
            kwhs.append(kw * hours)
        kwh = sum(kwhs)
        response['kwh'] = kwh
        if settings.ELECTRIC_CAR_RANGE_KM_PER_KWH:
            response['electric_car_range_km'] = kwh * settings.ELECTRIC_CAR_RANGE_KM_PER_KWH
        if settings.ELECTRICITY_COST_PER_KWH:
            response['electricity_cost_dollar'] = kwh * settings.ELECTRICITY_COST_PER_KWH
        if settings.COOLING_COST_PER_KWH:
            response['cooling_cost_dollar'] = kwh * settings.COOLING_COST_PER_KWH
        if settings.CO2_KG_PER_MWH:
            response['co2_emissions_kg'] = kwh / 1000 * settings.CO2_KG_PER_MWH

    if job.gpu_count() > 0:
        # Cost for a GPU job
        if settings.GPU_COST_PER_HOUR:
            response['hardware_cost_dollar'] = job.gpu_count() * settings.GPU_COST_PER_HOUR * hours

        if settings.CLOUD_GPU_COST_PER_HOUR:
            response['cloud_cost_dollar'] = job.gpu_count() * settings.CLOUD_GPU_COST_PER_HOUR * hours
    else:
        # Cost for a CPU job
        if settings.CPU_CORE_COST_PER_HOUR:
            response['hardware_cost_dollar'] = job.parse_tres_req()['total_cores'] * settings.CPU_CORE_COST_PER_HOUR * hours
        if settings.CLOUD_CPU_CORE_COST_PER_HOUR:
            response['cloud_cost_dollar'] = job.parse_tres_req()['total_cores'] * settings.CLOUD_CPU_CORE_COST_PER_HOUR * hours

    return JsonResponse(response)


class JobScriptViewSet(viewsets.ModelViewSet):
    queryset = JobScript.objects.all().order_by('-last_modified')
    serializer_class = JobScriptSerializer
    permission_classes = [permissions.IsAdminUser]
