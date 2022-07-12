from django.shortcuts import render
from django.http import JsonResponse
from userportal.common import staff, Prometheus, uid_to_username
from slurm.models import JobTable
from django.conf import settings
from django.contrib.auth.decorators import login_required
import time
from datetime import datetime, timedelta

prom = Prometheus(settings.PROMETHEUS)


@login_required
@staff
def index(request):
    return render(request, 'top/index.html')


def metrics_to_user(metrics):
    users_metrics = {}
    for line in metrics:
        users_metrics[line['metric']['user']] = line['value'][1]
    return users_metrics


def metrics_to_job(metrics):
    jobs_metrics = {}
    for line in metrics:
        jobs_metrics[line['metric']['slurmjobid']] = line['value'][1]
    return jobs_metrics


@login_required
@staff
def compute(request):
    context = {}

    query_cpu = 'topk(100, sum(slurm_job:allocated_core:count_user_account{{ {filter} }}) by (user))'.format(
        filter=prom.get_filter())
    stats_cpu = prom.query_last(query_cpu)
    cpu_users = []
    for line in stats_cpu:
        cpu_users.append(line['metric']['user'])
    stats_cpu_asked = metrics_to_user(stats_cpu)

    query_cpu_used = 'sum(slurm_job:used_core:sum_user_account{{user=~"{users}", {filter} }}) by (user)'.format(
        users='|'.join(cpu_users),
        filter=prom.get_filter())
    stats_cpu_used = metrics_to_user(prom.query_last(query_cpu_used))

    query_mem_asked = 'sum(slurm_job:allocated_memory:sum_user_account{{user=~"{users}", {filter}}}) by (user)'.format(
        users='|'.join(cpu_users),
        filter=prom.get_filter())
    stats_mem_asked = metrics_to_user(prom.query_last(query_mem_asked))
    query_mem_max = 'sum(slurm_job:max_memory:sum_user_account{{user=~"{users}", {filter}}}) by (user)'.format(
        users='|'.join(cpu_users),
        filter=prom.get_filter())
    stats_mem_max = metrics_to_user(prom.query_last(query_mem_max))

    context['cpu_users'] = []
    for line in stats_cpu:
        user = line['metric']['user']

        try:
            context['cpu_users'].append({
                'user': user,
                'cpu_asked': stats_cpu_asked[user],
                'cpu_used': stats_cpu_used[user],
                'cpu_ratio': float(stats_cpu_used[user]) / float(stats_cpu_asked[user]),
                'mem_asked': stats_mem_asked[user],
                'mem_max': stats_mem_max[user],
                'mem_ratio': int(stats_mem_max[user]) / int(stats_mem_asked[user]),
            })
        except KeyError:
            pass

    return render(request, 'top/compute.html', context)


@login_required
@staff
def gpucompute(request):
    context = {}

    query_gpu = 'topk(100, sum(slurm_job:allocated_gpu:count_user_account{{ {filter} }}) by (user))'.format(
        filter=prom.get_filter())
    stats_gpu = prom.query_last(query_gpu)
    gpu_users = []
    for line in stats_gpu:
        gpu_users.append(line['metric']['user'])

    stats_gpu_asked = metrics_to_user(stats_gpu)

    query_gpu_util = 'sum(slurm_job:used_gpu:sum_user_account{{user=~"{users}", {filter} }}) by (user)'.format(
        users='|'.join(gpu_users),
        filter=prom.get_filter())
    stats_gpu_util = metrics_to_user(prom.query_last(query_gpu_util))

    query_gpu_used = 'sum(slurm_job:non_idle_gpu:sum_user_account{{user=~"{users}", {filter}}}) by (user)'.format(
        users='|'.join(gpu_users),
        filter=prom.get_filter())
    stats_gpu_used = metrics_to_user(prom.query_last(query_gpu_used))

    context['gpu_users'] = []
    for line in stats_gpu:
        user = line['metric']['user']
        if user not in stats_gpu_used:
            # User is not using any GPU
            stats_gpu_used[user] = 0

        context['gpu_users'].append({
            'user': user,
            'gpu_asked': stats_gpu_asked[user],
            'gpu_util': stats_gpu_util[user],
            'gpu_used': stats_gpu_used[user],
            'gpu_ratio': float(stats_gpu_util[user]) / float(stats_gpu_asked[user]),
        })
    return render(request, 'top/gpucompute.html', context)


@login_required
@staff
def largemem(request):
    context = {}

    hour_ago = int(time.time()) - (3600)
    week_ago = int(time.time()) - (3600 * 24 * 7)

    jobs_running = JobTable.objects.filter(
        time_start__lt=hour_ago,
        time_eligible__gt=week_ago,  # until time_start is indexed...
        partition__icontains='large',
        state=1)

    jobs = []
    for job in jobs_running:
        jobs.append(str(job.id_job))

    query_cpu_asked = 'count(slurm_job_core_usage_total{{slurmjobid=~"{jobs}", {filter}}}) by (slurmjobid)'.format(
        jobs='|'.join(jobs),
        filter=prom.get_filter())
    stats_cpu_asked = metrics_to_job(prom.query_last(query_cpu_asked))
    query_cpu_used = 'sum(rate(slurm_job_core_usage_total{{slurmjobid=~"{jobs}", {filter}}}[2m]) / 1000000000) by (slurmjobid)'.format(
        jobs='|'.join(jobs),
        filter=prom.get_filter())
    stats_cpu_used = metrics_to_job(prom.query_last(query_cpu_used))

    query_mem_asked = 'sum(slurm_job_memory_limit{{slurmjobid=~"{jobs}", {filter}}}) by (slurmjobid)'.format(
        jobs='|'.join(jobs),
        filter=prom.get_filter())
    stats_mem_asked = metrics_to_job(prom.query_last(query_mem_asked))
    query_mem_max = 'sum(slurm_job_memory_max{{slurmjobid=~"{jobs}", {filter}}}) by (slurmjobid)'.format(
        jobs='|'.join(jobs),
        filter=prom.get_filter())
    stats_mem_max = metrics_to_job(prom.query_last(query_mem_max))

    context['jobs'] = []
    for job in jobs_running:
        try:
            job_id = str(job.id_job)

            mem_ratio = float(stats_mem_max[job_id]) / float(stats_mem_asked[job_id])
            cpu_ratio = float(stats_cpu_used[job_id]) / float(stats_cpu_asked[job_id])
            context['jobs'].append({
                'user': uid_to_username(job.id_user),
                'job_id': job.id_job,
                'time_start_dt': job.time_start_dt,
                'cpu_asked': stats_cpu_asked[job_id],
                'cpu_used': stats_cpu_used[job_id],
                'mem_asked': stats_mem_asked[job_id],
                'mem_max': stats_mem_max[job_id],
                'mem_ratio': mem_ratio,
                'cpu_ratio': cpu_ratio,
                'min_ratio': min(mem_ratio, cpu_ratio),
            })
        except IndexError:
            context['jobs'].append({
                'user': uid_to_username(job.id_user),
                'job_id': job.id_job,
                'mem_asked': 'error',
                'mem_max': 'error',
            })

    # put the worst jobs first
    context['jobs'].sort(key=lambda x: x['min_ratio'], reverse=False)
    return render(request, 'top/largemem.html', context)


@login_required
@staff
def lustre(request):
    context = {}

    # Could be autodetected with 'count(lustre_stats_total{component="mdt"}) by (target)'
    context['lustre_fs_names'] = settings.LUSTRE_FS_NAMES
    return render(request, 'top/lustre.html', context)


@login_required
@staff
def graph_lustre_mdt(request, fs):
    query = 'topk(5, sum by (user) (rate(lustre_job_stats_total{{instance=~"{fs}-mds.*", user!="root", {filter}}}[5m])))'.format(
        fs=fs,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), datetime.now())
    data = {'lines': []}
    for line in stats:
        try:
            user = line['metric']['user']
        except KeyError:
            user = 'others'
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': user
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' IOPS'
        }
    }
    return JsonResponse(data)


@login_required
@staff
def graph_lustre_ost(request, fs):
    data = {'lines': []}
    for rw in ['read', 'write']:
        query = 'topk(5, sum by (user) (rate(lustre_job_{rw}_bytes_total{{target=~"{fs}.*", {filter}}}[5m])))/1024/1024'.format(
            rw=rw,
            fs=fs,
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), datetime.now())

        for line in stats:
            try:
                user = line['metric']['user']
            except KeyError:
                user = 'others'
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if rw == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]

            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(rw, user)
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' MiB/s'
        }
    }
    return JsonResponse(data)
