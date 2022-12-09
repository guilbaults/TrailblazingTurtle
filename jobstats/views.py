from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound, JsonResponse
from slurm.models import JobTable, AssocTable
from userportal.common import user_or_staff, username_to_uid, Prometheus, request_to_username, compute_allocations_by_user, get_step
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from rest_framework import viewsets
from rest_framework import permissions
from jobstats.models import JobScript
from jobstats.serializers import JobSerializer, JobScriptSerializer
from notes.models import Note
import statistics
from jobstats.analyze_job import find_loaded_modules, analyze_jobscript
from jobstats.analyze_job import Comment
from django.http import Http404

GPU_MEMORY = {
    'GRID V100D-4C': 4,
    'GRID V100D-8C': 8,
    'GRID V100D-16C': 16,
    'GRID V100D-32C': 32,
    'Tesla V100-SXM2-16GB': 16,
    'NVIDIA A100-SXM4-40GB': 40,
}
GPU_FULL_POWER = {'Tesla V100-SXM2-16GB': 300, 'NVIDIA A100-SXM4-40GB': 400}
GPU_IDLE_POWER = {'Tesla V100-SXM2-16GB': 55, 'NVIDIA A100-SXM4-40GB': 55}
GPU_SHORT_NAME = {
    'GRID V100D-4C': 'V100 4GB',
    'GRID V100D-8C': 'V100 8GB',
    'GRID V100D-16C': 'V100 16GB',
    'GRID V100D-32C': 'V100 32GB',
    'Tesla V100-SXM2-16GB': 'V100',
    'NVIDIA A100-SXM4-40GB': 'A100',
}

prom = Prometheus(settings.PROMETHEUS)


def sanitize_step(request, minimum=30):
    # all in seconds, will return the smallest interval allowed to drap a graph
    return max(int(request.GET.get('step')), minimum)


def jobid_str_to_list(jobid_str):
    # split range of jobids in format 100-105,107,109,110-120 to a list of jobids
    jobs_blocks = jobid_str.split(',')
    jobs = []
    for block in jobs_blocks:
        if '-' in block:
            start, end = block.split('-')
            jobs += range(int(start), int(end) + 1)
        else:
            jobs.append(int(block))
    return jobs


def get_start_end_jobs(jobs):
    start = None
    end = None

    for job in jobs:
        if start is None or job.time_start_dt() < start:
            start = job.time_start_dt()
        if end is None or job.time_end_dt() > end:
            end = job.time_end_dt()

    return start, end


def get_job_ids(jobs):
    return [job.id_job for job in jobs]


def get_job_ids_regex(jobs):
    return '|'.join([str(job.id_job) for job in jobs])


def context_job_info(username, job_id):
    context = {'job_id': job_id, 'username': username}
    uid = username_to_uid(username)
    context['uid'] = uid
    jobs = JobTable.objects.filter(id_user=uid).filter(id_job__in=jobid_str_to_list(job_id)).all()
    if len(jobs) == 0:
        raise Http404()
    elif len(jobs) > 1:
        context['multiple_jobs'] = True
        start, end = get_start_end_jobs(jobs)
        if end is None:
            end = datetime.now()

        # Create a fake job with the start and end times of the first and last job
        context['job'] = JobTable(
            id_job=job_id,
            id_user=uid,
            time_start=start.timestamp(),
            time_end=end.timestamp(),
        )

        context['step'] = get_step(start, end)
        context['jobs'] = jobs
        context['id_regex'] = get_job_ids_regex(context['jobs'])
        context['gpu_count'] = 0
        for job in jobs:
            context['gpu_count'] += job.gpu_count()
    else:
        context['job'] = jobs[0]
        context['multiple_jobs'] = False
        context['id_regex'] = str(context['job'].id_job)
        context['step'] = get_step(context['job'].time_start_dt(), context['job'].time_end_dt())
        context['gpu_count'] = context['job'].gpu_count()
    return context


def instances_regex(context):
    return '|'.join([s + '(:.*)?' for s in context['job'].nodes()])


@login_required
def index(request):
    return redirect('{}/'.format(request_to_username(request)))


@login_required
@user_or_staff
def user(request, username):
    uid = username_to_uid(username)
    context = {'username': username}

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
        query_cpu = 'sum(rate(slurm_job_core_usage_total{{user="{}", {}}}[{}s]) / 1000000000)'.format(username, prom.get_filter(), prom.rate('slurm-job-exporter'))
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

    if request.user.is_staff:
        context['notes'] = Note.objects.filter(username=username).filter(deleted_at=None).order_by('-modified_at')

    return render(request, 'jobstats/user.html', context)


@login_required
@user_or_staff
def job(request, username, job_id):
    context = context_job_info(username, job_id)

    if context['multiple_jobs']:
        return render(request, 'jobstats/job.html', context)

    # continue with single job
    job = context['job']

    # Adjust the precision of the graphs.
    context['step'] = get_step(job.time_start_dt(), job.time_end_dt())

    if request.user.is_staff:
        context['notes'] = Note.objects.filter(job_id=job_id).filter(deleted_at=None).order_by('-modified_at')

    context['tres_req'] = job.parse_tres_req()
    context['total_mem'] = context['tres_req']['total_mem'] * 1024 * 1024

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
            context['priority'] = None
        except IndexError:
            context['priority'] = None

    if job.time_start_dt() is None:
        return render(request, 'jobstats/job.html', context)

    try:
        query_cpu = 'sum(rate(slurm_job_core_usage_total{{slurmjobid="{}", {}}}[{}s]) / 1000000000)'.format(job_id, prom.get_filter(), prom.rate('slurm-job-exporter'))
        stats_cpu = prom.query_prometheus(query_cpu, job.time_start_dt(), job.time_end_dt())
        context['cpu_used'] = statistics.mean(stats_cpu[1])
    except ValueError:
        context['cpu_used'] = None

    try:
        query_mem = 'sum(slurm_job_memory_max{{slurmjobid="{}", {}}})'.format(job_id, prom.get_filter())
        stats_mem = prom.query_prometheus(query_mem, job.time_start_dt(), job.time_end_dt())
        context['mem_used'] = max(stats_mem[1])
    except ValueError:
        context['mem_used'] = None

    if context['gpu_count'] > 0:
        try:
            query_gpu_util = 'sum(slurm_job_utilization_gpu{{slurmjobid="{}", {}}})'.format(job_id, prom.get_filter())
            stats_gpu_util = prom.query_prometheus(query_gpu_util, job.time_start_dt(), job.time_end_dt())
            context['gpu_used'] = statistics.mean(stats_gpu_util[1])
        except ValueError:
            context['gpu_used'] = None

        try:
            query_gpu_mem = 'sum(slurm_job_memory_usage_gpu{{slurmjobid="{}", {}}})/(1024*1024*1024)'.format(job_id, prom.get_filter())
            stats_gpu_mem = prom.query_prometheus(query_gpu_mem, job.time_start_dt(), job.time_end_dt())
            context['gpu_mem'] = max(stats_gpu_mem[1]) / GPU_MEMORY[job.gpu_type()] * 100
        except ValueError:
            context['gpu_mem'] = None

        try:
            query_gpu_power = 'sum(slurm_job_power_gpu{{slurmjobid="{}", {}}})/(1000)'.format(job_id, prom.get_filter())
            stats_gpu_power = prom.query_prometheus(query_gpu_power, job.time_start_dt(), job.time_end_dt())
            used_power = statistics.mean(stats_gpu_power[1]) - GPU_IDLE_POWER[job.gpu_type()]
            context['gpu_power'] = used_power / GPU_FULL_POWER[job.gpu_type()] * 100
        except ValueError:
            context['gpu_power'] = None

    comments = []
    try:
        context['job_script'] = JobScript.objects.get(id_job=job_id)
        try:
            modules = find_loaded_modules(context['job_script'].submit_script)
            context['loaded_modules'] = modules
            comments += analyze_jobscript(context['job_script'].submit_script, context['loaded_modules'], job)
        except ValueError:
            context['loaded_modules'] = None  # Could not parse jobscript to find loaded modules
    except JobScript.DoesNotExist:
        context['job_script'] = None

    if context['cpu_used'] is not None:
        if context['cpu_used'] < 1 and context['tres_req']['total_cores'] > 1:
            comments += [Comment(
                _('Less than 1 core was used on average but {} were asked for, this look like a serial job').format(context['tres_req']['total_cores']),
                'critical',
                'https://docs.alliancecan.ca/wiki/Running_jobs#Serial_job',
                graph_ids=['cpu'])]

        if (context['tres_req']['total_cores'] / 2) > context['cpu_used']:
            comments += [Comment(
                _('Less than half the CPU compute cycle were used').format(context['tres_req']['total_cores']),
                'critical',
                graph_ids=['cpu'])]

    if context['mem_used'] is not None:
        if context['total_mem'] / 10 > context['mem_used']:
            comments += [Comment(
                _('Less than 10% of the asked memory was used, please adjust the amount of memory requested'),
                'critical',
                graph_ids=['mem'])]

    if job.state == JobTable.StatesJob.COMPLETE:
        if job.timelimit < 60:  # in minutes
            comments += [Comment(
                _('Less than 1 hour was asked, please packages your short jobs with GLOST or GNU parallel if you want to run 100+ short jobs'),
                'critical',
                'https://docs.alliancecan.ca/wiki/GLOST')]
        elif job.used_time() < 3600:
            comments += [Comment(
                _('Less than 1 hour was used, please packages your short jobs with GLOST or GNU parallel if you want to run 100+ short jobs'),
                'warning',
                'https://docs.alliancecan.ca/wiki/GLOST')]

    if job.state == JobTable.StatesJob.OOM:
        comments += [Comment(
            _('Out of memory, increase memory asked and retry this job'),
            'critical',
            graph_ids=['mem'])]

    if job.state == JobTable.StatesJob.NODE_FAIL:
        comments += [Comment(
            _('Node failure, this is a temporary issue and probably not caused by the job'),
            'critical')]

    if len(job.nodes()) > 1:
        comments += [Comment(
            _('This job is using multiple nodes'),
            'info')]

    try:
        query_threads = 'sum(slurm_job_threads_count{{slurmjobid=~"{}", state="running", {}}})'.format(job_id, prom.get_filter())
        stats_threads = prom.query_prometheus(query_threads, job.time_start_dt(), job.time_end_dt())
        running_threads = statistics.mean(stats_threads[1])
        if running_threads > 1.25 * context['tres_req']['total_cores']:
            comments += [Comment(
                _('This job is running on average {:.1f} threads on {} cores, the cores might be oversubscribed').format(
                    running_threads, context['tres_req']['total_cores']),
                'warning',
                graph_ids=['thread'])]
        elif running_threads < 0.75 * context['tres_req']['total_cores']:
            comments += [Comment(
                _('This job is running on average {:.1f} threads on {} cores, the cores might be underused').format(
                    running_threads, context['tres_req']['total_cores']),
                'warning',
                graph_ids=['thread'])]
    except ValueError:
        pass

    context['comments'] = sorted(comments, key=lambda x: x.line_number)

    context['graph_div'] = {}
    for comment in comments:
        for graph in comment.graph_ids:
            context['graph_div'][graph] = comment.display_card_class()

    return render(request, 'jobstats/job.html', context)


@login_required
@user_or_staff
def graph_cpu(request, username, job_id):
    context = context_job_info(username, job_id)

    query = 'rate(slurm_job_core_usage_total{{slurmjobid=~"{}", {}}}[{}s]) / 1000000000'.format(context['id_regex'], prom.get_filter(), prom.rate('slurm-job-exporter'))
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    data = {'lines': []}
    for line in stats:
        core_num = int(line['metric']['core'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if context['multiple_jobs']:
            name = '{} core {} {}'.format(line['metric']['slurmjobid'], core_num, compute_name)
        else:
            name = 'core {} {}'.format(core_num, compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': name,
            'hovertemplate': '%{y:.1f}',
        })

    if context['multiple_jobs']:
        query_count = 'count(slurm_job_core_usage_total{{slurmjobid=~"{}", {}}})'.format(context['id_regex'], prom.get_filter())
        line = prom.query_prometheus(
            query_count,
            context['job'].time_start_dt(),
            context['job'].time_end_dt(),
            step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line[0]))
        y = line[1]
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Allocated cores'),
            'hovertemplate': '%{y:.1f}',
        })
    else:
        data['layout'] = {
            'yaxis': {
                'title': _('Cores'),
                'range': [0, context['job'].parse_tres_req()['total_cores']],
            }
        }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_cpu_user(request, username):
    data = {'lines': []}
    try:
        query_used = 'sum(rate(slurm_job_core_usage_total{{user="{}", {}}}[{}s])) / 1000000000'.format(username, prom.get_filter(), prom.rate('slurm-job-exporter'))
        stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
            'y': stats_used[1],
            'type': 'scatter',
            'name': _('Used'),
            'hovertemplate': '%{y:.1f}',
        })

        query_alloc = 'sum(count(slurm_job_core_usage_total{{user="{}", {}}}))'.format(username, prom.get_filter())
        stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
            'y': stats_alloc[1],
            'type': 'scatter',
            'name': _('Allocated'),
            'hovertemplate': '%{y:.1f}',
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
            'name': _('Allocated'),
            'hovertemplate': '%{y:.1f}',
        })

        query_max = 'sum(slurm_job_memory_max{{user="{}", {}}})/(1024*1024*1024)'.format(username, prom.get_filter())
        stats_max = prom.query_prometheus(query_max, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_max[0])),
            'y': stats_max[1],
            'type': 'scatter',
            'name': _('Max used'),
            'hovertemplate': '%{y:.1f}',
        })

        query_used = 'sum(slurm_job_memory_usage{{user="{}", {}}})/(1024*1024*1024)'.format(username, prom.get_filter())
        stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
            'y': stats_used[1],
            'type': 'scatter',
            'name': _('Used'),
            'hovertemplate': '%{y:.1f}',
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
    context = context_job_info(username, job_id)

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
        query = '{}{{slurmjobid=~"{}", {}}}/(1024*1024*1024)'.format(stat[0], context['id_regex'], prom.get_filter())
        stats = prom.query_prometheus_multiple(
            query,
            context['job'].time_start_dt(),
            context['job'].time_end_dt(),
            step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))
        for line in stats:
            compute_name = line['metric']['instance'].split(':')[0]
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            if context['multiple_jobs']:
                name = '{} {} {}'.format(line['metric']['slurmjobid'], stat[1], compute_name)
            else:
                name = '{} {}'.format(stat[1], compute_name)
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': name,
                'hovertemplate': '%{y:.1f}',
            })
        if stat[0] == 'slurm_job_memory_limit':
            maximum = max(max(map(lambda x: x['y'], stats)))

    if context['multiple_jobs']:
        query_count = 'sum(slurm_job_memory_limit{{slurmjobid=~"{}", {}}})/(1024*1024*1024)'.format(context['id_regex'], prom.get_filter())
        line = prom.query_prometheus(
            query_count,
            context['job'].time_start_dt(),
            context['job'].time_end_dt(),
            step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line[0]))
        y = line[1]
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Allocated memory'),
            'hovertemplate': '%{y:.1f}',
        })
        maximum = max(y)

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
def graph_thread(request, username, job_id):
    context = context_job_info(username, job_id)

    data = {'lines': []}

    query_procs = 'slurm_job_process_count{{slurmjobid=~"{}", {}}}'.format(context['id_regex'], prom.get_filter())
    stats_procs = prom.query_prometheus_multiple(
        query_procs,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))
    for line in stats_procs:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if context['multiple_jobs']:
            name = '{} {} {}'.format(line['metric']['slurmjobid'], _('Processes'), compute_name)
        else:
            name = '{} {}'.format(_('Processes'), compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f}',
        })

    query_threads = 'slurm_job_threads_count{{slurmjobid=~"{}", {}}}'.format(context['id_regex'], prom.get_filter())
    stats_threads = prom.query_prometheus_multiple(
        query_threads,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))
    for line in stats_threads:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']

        try:
            # handle the slightly different format in slurm-job-exporter v0.0.11, fixed in v0.0.12
            state = line['metric']['state']
        except KeyError:
            state = 'total'

        if context['multiple_jobs']:
            name = '{} {} {} {}'.format(line['metric']['slurmjobid'], _('Threads'), compute_name, state)
        else:
            name = '{} {} {}'.format(_('Threads'), compute_name, state)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f}',
        })

    data['layout'] = {
        'yaxis': {
            'title': _('Processes and threads'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_lustre_mdt(request, username, job_id):
    context = context_job_info(username, job_id)

    query = 'sum(rate(lustre_job_stats_total{{component="mdt",jobid=~"{job_id}", {filter}}}[{step}s])) by (operation, fs, jobid) !=0'.format(
        job_id=context['id_regex'],
        step=sanitize_step(request, minimum=prom.rate('lustre_exporter')),
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('lustre_exporter')))

    data = {'lines': []}
    for line in stats:
        operation = line['metric']['operation']
        fs = line['metric']['fs']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if context['multiple_jobs']:
            name = '{} {} {}'.format(line['metric']['jobid'], operation, fs)
        else:
            name = '{} {}'.format(operation, fs)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': name,
            'hovertemplate': '%{y:.1f}',
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
    query = 'sum(rate(lustre_job_stats_total{{component=~"mdt",user=~"{}", {}}}[{}s])) by (operation, fs) !=0'.format(username, prom.get_filter(), prom.rate('lustre_exporter'))
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
            'name': '{} {}'.format(operation, fs),
            'hovertemplate': '%{y:.1f}',
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
    context = context_job_info(username, job_id)

    data = {'lines': []}
    for i in ['read', 'write']:
        query = '(sum(rate(lustre_job_{i}_bytes_total{{component="ost",jobid=~"{job_id}",target=~".*-OST.*", {filter}}}[{step}s])) by (fs, jobid)) / (1024*1024)'.format(
            i=i,
            job_id=context['id_regex'],
            step=sanitize_step(request, minimum=prom.rate('lustre_exporter')),
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(
            query,
            context['job'].time_start_dt(),
            context['job'].time_end_dt(),
            step=sanitize_step(request, minimum=prom.rate('lustre_exporter')))

        for line in stats:
            fs = line['metric']['fs']
            if i == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if context['multiple_jobs']:
                name = '{} {} {}'.format(line['metric']['jobid'], i, fs)
            else:
                name = '{} {}'.format(i, fs)
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': name,
                'hovertemplate': '%{y:.1f}',
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
        query = '(sum(rate(lustre_job_{}_bytes_total{{component=~"ost",user=~"{}",target=~".*-OST.*", {}}}[{}s])) by (fs)) / (1024*1024)'.format(
            i,
            username,
            prom.get_filter(),
            prom.rate('lustre_exporter'))
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), datetime.now())

        for line in stats:
            fs = line['metric']['fs']
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if i == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': '{} {}'.format(i, fs),
                'hovertemplate': '%{y:.1f}',
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
    context = context_job_info(username, job_id)

    data = {'lines': []}

    queries = [
        ('slurm_job_utilization_gpu', _('SM Active')),
        ('slurm_job_sm_occupancy_gpu', _('SM Occupancy')),
        ('slurm_job_tensor_gpu', _('Tensor')),
        ('slurm_job_fp64_gpu', _('FP64')),
        ('slurm_job_fp32_gpu', _('FP32')),
        ('slurm_job_fp16_gpu', _('FP16')),
    ]

    for q in queries:
        query = '{}{{slurmjobid=~"{}", {}}}'.format(q[0], context['id_regex'], prom.get_filter())
        stats = prom.query_prometheus_multiple(
            query,
            context['job'].time_start_dt(),
            context['job'].time_end_dt(),
            step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

        for line in stats:
            gpu_num = int(line['metric']['gpu'])
            compute_name = line['metric']['instance'].split(':')[0]
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            if context['multiple_jobs']:
                name = '{} {} GPU {} {}'.format(line['metric']['slurmjobid'], q[1], gpu_num, compute_name)
            else:
                name = '{} GPU {} {}'.format(q[1], gpu_num, compute_name)
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': name,
                'hovertemplate': '%{y:.1f}%',
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
        'name': _('Allocated'),
        'hovertemplate': '%{y:.1f}',
    })

    query_used = 'sum(slurm_job_utilization_gpu{{user="{}", {}}})/100'.format(username, prom.get_filter())
    stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
        'y': stats_used[1],
        'type': 'scatter',
        'name': _('Used'),
        'hovertemplate': '%{y:.1f}',
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
    context = context_job_info(username, job_id)

    query = 'slurm_job_utilization_gpu_memory{{slurmjobid=~"{}", {}}}'.format(context['id_regex'], prom.get_filter())
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if context['multiple_jobs']:
            name = '{} GPU {} {}'.format(line['metric']['slurmjobid'], gpu_num, compute_name)
        else:
            name = 'GPU {} {}'.format(gpu_num, compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f}%',
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
    context = context_job_info(username, job_id)

    query = 'slurm_job_memory_usage_gpu{{slurmjobid=~"{}", {}}} /(1024*1024*1024)'.format(context['id_regex'], prom.get_filter())
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        gpu_type = line['metric']['gpu_type']
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if context['multiple_jobs']:
            name = '{} GPU {} {}'.format(line['metric']['slurmjobid'], gpu_num, compute_name)
        else:
            name = '{} GPU {}'.format(gpu_num, compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f} GiB',
        })
    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' GiB',
            'range': [0, GPU_MEMORY[gpu_type]],
            'title': _('GPU Memory'),
        }
    }
    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_power(request, username, job_id):
    context = context_job_info(username, job_id)

    query = 'slurm_job_power_gpu{{slurmjobid=~"{}", {}}}/1000'.format(context['id_regex'], prom.get_filter())
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    data = {'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        gpu_type = line['metric']['gpu_type']
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if context['multiple_jobs']:
            name = '{} {} GPU {} {}'.format(line['metric']['slurmjobid'], gpu_type, gpu_num, compute_name)
        else:
            name = '{} {} GPU {}'.format(gpu_type, gpu_num, compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f} W',
        })

    if len(stats) > 0:
        data['lines'].append({
            'x': x,
            'y': [GPU_IDLE_POWER[gpu_type] for x in y],
            'type': 'scatter',
            'name': '{} {}'.format(_('Idle power'), GPU_SHORT_NAME[gpu_type]),
            'hovertemplate': '%{y:.1f} W',
        })

        data['layout'] = {
            'yaxis': {
                'ticksuffix': ' W',
                'range': [0, GPU_FULL_POWER[gpu_type]],
                'title': _('GPU Power'),
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
            'name': '{} {}'.format(_('Allocated'), GPU_SHORT_NAME[gpu_type]),
            'hovertemplate': '%{y:.1f} W',
        })

        data['lines'].append({
            'x': x,
            'y': [GPU_IDLE_POWER[gpu_type] * z for z in y],
            'type': 'scatter',
            'name': '{} {}'.format(_('Idle power'), GPU_SHORT_NAME[gpu_type]),
            'hovertemplate': '%{y:.1f} W',
        })

    query_used = 'sum(slurm_job_power_gpu{{user="{}", {}}}) by (gpu_type) / 1000'.format(username, prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, datetime.now() - timedelta(hours=6), datetime.now())
    for line in stats_used:
        gpu_type = line['metric']['gpu_type']
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': '{} {}'.format(_('Used'), GPU_SHORT_NAME[gpu_type]),
            'hovertemplate': '%{y:.1f} W',
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'W',
            'title': _('GPU Power'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_pcie(request, username, job_id):
    context = context_job_info(username, job_id)

    data = {'lines': []}
    query = 'rate(slurm_job_pcie_gpu_total{{slurmjobid=~"{}", {}}}[{}s])'.format(
        context['id_regex'],
        prom.get_filter(),
        prom.rate('slurm-job-exporter'))
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        direction = line['metric']['direction']
        if direction == 'RX':
            y = line['y']
        else:
            y = [-x for x in line['y']]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        if context['multiple_jobs']:
            name = '{} {} GPU {} {}'.format(line['metric']['slurmjobid'], direction, gpu_num, compute_name)
        else:
            name = '{} {} GPU {}'.format(direction, gpu_num, compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f}',
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
def graph_gpu_nvlink(request, username, job_id):
    context = context_job_info(username, job_id)

    data = {'lines': []}
    query = 'rate(slurm_job_nvlink_gpu_total{{slurmjobid="{}", {}}}[{}s])'.format(
        context['id_regex'],
        prom.get_filter(),
        prom.rate('slurm-job-exporter'))
    stats = prom.query_prometheus_multiple(
        query,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        direction = line['metric']['direction']
        if direction == 'RX':
            y = line['y']
        else:
            y = [-x for x in line['y']]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        if context['multiple_jobs']:
            name = '{} {} GPU {} {}'.format(line['metric']['slurmjobid'], direction, gpu_num, compute_name)
        else:
            name = '{} {} GPU {}'.format(direction, gpu_num, compute_name)
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f}',
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
def graph_infiniband_bdw(request, username, job_id):
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    data = {'lines': []}
    step = sanitize_step(request, minimum=prom.rate('node_exporter'))

    query_received = 'rate(node_infiniband_port_data_received_bytes_total{{instance=~"{instances}", {filter}}}[{step}s]) * 8 / (1000*1000*1000)'.format(
        instances=instances,
        filter=prom.get_filter(),
        step=step)
    stats_received = prom.query_prometheus_multiple(query_received, context['job'].time_start_dt(), context['job'].time_end_dt(), step=step)
    for line in stats_received:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Received {}'.format(compute_name),
            'hovertemplate': '%{y:.1f}',
        })

    query_transmitted = '-rate(node_infiniband_port_data_transmitted_bytes_total{{instance=~"{instances}", {filter}}}[{step}s]) * 8 /(1000*1000*1000)'.format(
        instances=instances,
        filter=prom.get_filter(),
        step=step)
    stats_transmitted = prom.query_prometheus_multiple(query_transmitted, context['job'].time_start_dt(), context['job'].time_end_dt(), step=step)
    for line in stats_transmitted:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Transmitted {}'.format(compute_name),
            'hovertemplate': '%{y:.1f}',
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
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    data = {'lines': []}
    step = sanitize_step(request, minimum=prom.rate('node_exporter'))

    query_read = 'rate(node_disk_reads_completed_total{{instance=~"{}",device=~"nvme.n.|sd.|vd.", {}}}[{}s])'.format(instances, prom.get_filter(), step)
    stats_read = prom.query_prometheus_multiple(query_read, context['job'].time_start_dt(), context['job'].time_end_dt(), step=step)
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
            'name': 'Read {}'.format(compute_name),
            'hovertemplate': '%{y:.1f} IOPS',
        })

    query_write = 'rate(node_disk_writes_completed_total{{instance=~"{}",device=~"nvme.n.|sd.|vd.", {}}}[{}s])'.format(instances, prom.get_filter(), step)
    stats_write = prom.query_prometheus_multiple(query_write, context['job'].time_start_dt(), context['job'].time_end_dt(), step=step)
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
            'name': 'Write {}'.format(compute_name),
            'hovertemplate': '%{y:.1f} IOPS',
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
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    data = {'lines': []}
    step = sanitize_step(request, minimum=prom.rate('node_exporter'))

    query_read = 'rate(node_disk_read_bytes_total{{instance=~"{instances}",device=~"nvme.n.|sd.|vd.", {filter}}}[{step}s])'.format(
        instances=instances,
        filter=prom.get_filter(),
        step=step)
    stats_read = prom.query_prometheus_multiple(query_read, context['job'].time_start_dt(), context['job'].time_end_dt(), step=step)
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
            'name': 'Read {}'.format(compute_name),
            'hovertemplate': '%{y:.1f}',
        })

    query_write = '-rate(node_disk_written_bytes_total{{instance=~"{instances}",device=~"nvme.n.|sd.|vd.", {filter}}}[{step}s])'.format(
        instances=instances,
        filter=prom.get_filter(),
        step=step)
    stats_write = prom.query_prometheus_multiple(query_write, context['job'].time_start_dt(), context['job'].time_end_dt(), step=step)
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
            'name': 'Write {}'.format(compute_name),
            'hovertemplate': '%{y:.1f}',
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
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    data = {'lines': []}

    query_disk = '(node_filesystem_size_bytes{{instance=~"{instances}",mountpoint="/localscratch", {filter}}} - node_filesystem_avail_bytes{{instance=~"{instances}",mountpoint="/localscratch", {filter}}})/(1000*1000*1000)'.format(
        instances=instances,
        filter=prom.get_filter())
    stats_disk = prom.query_prometheus_multiple(query_disk, context['job'].time_start_dt(), context['job'].time_end_dt(), step=sanitize_step(request, minimum=prom.rate('node_exporter')))
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
            'name': compute_name,
            'hovertemplate': '%{y:.1f} GB',
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' GB',
            'title': _('Disk'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_mem_bdw(request, username, job_id):
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    data = {'lines': []}

    for direction in ['Reads', 'Writes']:
        query = 'rate(DRAM_{direction}{{instance=~"{instances}", {filter} }}[1m])/1024/1024/1024'.format(
            direction=direction,
            instances=instances,
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(query, context['job'].time_start_dt(), context['job'].time_end_dt(), step=sanitize_step(request, minimum=prom.rate('pcm-sensor-server')))
        for line in stats:
            if 'socket' not in line['metric']:
                continue
            compute_name = "{} {} socket {}".format(
                direction,
                line['metric']['instance'].split(':')[0],
                line['metric']['socket'])
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': compute_name,
                'hovertemplate': '%{y:.1f} GB/s',
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' GB/s',
            'title': _('Memory bandwidth'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_l2_rate(request, username, job_id):
    return graph_cache_rate(request, username, job_id, 'L2')


@login_required
@user_or_staff
def graph_l3_rate(request, username, job_id):
    return graph_cache_rate(request, username, job_id, 'L3')


def map_pcm_cores(request, context):
    instances = instances_regex(context)
    # get the OS core mapping to the physical cores since they don't match
    query_mapping = 'OS_ID{{instance=~"{instances}", {filter}}}'.format(
        instances=instances,
        filter=prom.get_filter())
    stats_mapping = prom.query_prometheus_multiple(
        query_mapping,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('pcm-sensor-server')))

    all_cores_mapping = {}  # key is the OS core, value is the (socket, core, thread)
    reverse_mapping = {}  # key is the (socket, core, thread), value is the OS core
    for line in stats_mapping:
        os_core = int(line['y'][0])  # This is the core number as seen by the OS
        instance = line['metric']['instance'].split(':')[0]
        phys_core = (
            int(line['metric']['socket']),
            int(line['metric']['core']),
            int(line['metric']['thread']))
        if instance not in all_cores_mapping:
            all_cores_mapping[instance] = {}
        all_cores_mapping[instance][os_core] = phys_core

        if instance not in reverse_mapping:
            reverse_mapping[instance] = {}
        reverse_mapping[instance][phys_core] = os_core

    # A bit of a waste, we only need the core used by the job and not the time series
    query_cpu = 'rate(slurm_job_core_usage_total{{slurmjobid=~"{}", {}}}[{}s]) / 1000000000'.format(
        context['id_regex'],
        prom.get_filter(),
        prom.rate('slurm-job-exporter'))
    stats_cpu = prom.query_prometheus_multiple(
        query_cpu,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('slurm-job-exporter')))

    used_mapping = {}
    for line in stats_cpu:
        instance = line['metric']['instance'].split(':')[0]
        if instance not in used_mapping:
            used_mapping[instance] = set()  # the set of physical cores/sockets used by the job
        used_mapping[instance].add(all_cores_mapping[instance][int(line['metric']['core'])])

    return used_mapping, reverse_mapping


def filter_stats(stats, used_mapping, reverse_mapping):
    filtered_stats = []
    data = {'lines': []}
    for line in stats:
        instance = line['metric']['instance'].split(':')[0]
        phys_core = (int(line['metric']['socket']), int(line['metric']['core']), int(line['metric']['thread']))
        if phys_core in used_mapping[instance]:
            filtered_stats.append(line)

    for line in filtered_stats:
        phys_core = (int(line['metric']['socket']), int(line['metric']['core']), int(line['metric']['thread']))
        compute_name = "{} core {}".format(
            line['metric']['instance'].split(':')[0],
            reverse_mapping[line['metric']['instance'].split(':')[0]][phys_core])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': compute_name,
            'hovertemplate': '%{y:.1f}',
        })
    return data


def graph_cache_rate(request, username, job_id, l_cache):
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    used_mapping, reverse_mapping = map_pcm_cores(request, context)

    # get all the L3 cache hits and misses, we will discard the ones not used
    # by the job since we can't easily filter them out with a regex in the query
    query_cache = 'rate({l_cache}_Cache_Hits{{instance=~"{instances}", core=~"[0-9]+", {filter}}}[{rate}s])/(rate({l_cache}_Cache_Hits{{instance=~"{instances}", core=~"[0-9]+", {filter}}}[{rate}s]) + rate({l_cache}_Cache_Misses{{instance=~"{instances}", core=~"[0-9]+", {filter}}}[{rate}s])) * 100'.format(
        l_cache=l_cache,
        instances=instances,
        filter=prom.get_filter(),
        rate=prom.rate('pcm-sensor-server'))
    stats_cache = prom.query_prometheus_multiple(
        query_cache,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('pcm-sensor-server')))

    # from all the L3 cache hits and misses, keep only the ones used by the job
    data = filter_stats(stats_cache, used_mapping, reverse_mapping)

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' %',
            'range': [0, 100],
            'title': _('Hit rate'),
        }
    }

    return JsonResponse(data)


def graph_ipc(request, username, job_id):
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    used_mapping, reverse_mapping = map_pcm_cores(request, context)

    # Retired instructions are the number of instructions that were executed
    # This is ignoring speculative instructions that were not used
    # https://www.intel.com/content/www/us/en/develop/documentation/vtune-help/top/analyze-performance/custom-analysis/custom-analysis-options/hardware-event-list/instructions-retired-event.html

    # We compute the IPC instead of the CPI to show a graph with "higher is better"
    # so read that documentation and invert their formula and ratio
    # https://www.intel.com/content/www/us/en/develop/documentation/vtune-help/top/reference/cpu-metrics-reference.html#cpu-metrics-reference_CLOCKTICKS-PER-INSTRUCTIONS-RETIRED-CPI
    query_ipc = 'rate(Instructions_Retired_Any{{instance=~"{instances}",core=~"[0-9]+", {filter} }}[{rate}s]) / rate(Clock_Unhalted_Ref{{instance=~"{instances}",core=~"[0-9]+", {filter} }}[{rate}s])'.format(
        instances=instances,
        filter=prom.get_filter(),
        rate=prom.rate('pcm-sensor-server'))
    stats_ipc = prom.query_prometheus_multiple(
        query_ipc,
        context['job'].time_start_dt(),
        context['job'].time_end_dt(),
        step=sanitize_step(request, minimum=prom.rate('pcm-sensor-server')))

    data = filter_stats(stats_ipc, used_mapping, reverse_mapping)

    data['layout'] = {
        'yaxis': {
            'title': _('IPC'),
        }
    }

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_cpu_interconnect(request, username, job_id):
    context = context_job_info(username, job_id)
    instances = instances_regex(context)

    data = {'lines': []}

    # Only measuring the incoming traffic, not the outgoing one since it's only a p2p connection
    query = '(rate(Incoming_Data_Traffic_On_Link_0{{instance=~"{instances}", {filter} }}[{rate}s]) + rate(Incoming_Data_Traffic_On_Link_1{{instance=~"{instances}", {filter} }}[{rate}s]) + rate(Incoming_Data_Traffic_On_Link_2{{instance=~"{instances}", {filter} }}[{rate}s]))/1024/1024/1024'.format(
        instances=instances,
        filter=prom.get_filter(),
        rate=prom.rate('pcm-sensor-server'))
    stats = prom.query_prometheus_multiple(query, context['job'].time_start_dt(), context['job'].time_end_dt(), step=sanitize_step(request, minimum=prom.rate('pcm-sensor-server')))
    for line in stats:
        compute_name = "Received {} socket {}".format(
            line['metric']['instance'].split(':')[0],
            line['metric']['socket'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': compute_name,
            'hovertemplate': '%{y:.1f} GB/s',
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' GB/s',
            'title': _('CPU interconnect bandwidth'),
        }
    }

    return JsonResponse(data)


def power(job, step):
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
        nodes_node_exporter = '|'.join([s + '(:.*)?' for s in nodes])
        query = '(label_replace(sum(redfish_chassis_power_average_consumed_watts{{instance=~"({nodes})-oob", {filter} }}) by (instance), "instance", "$1", "instance", "(.*)-oob") ) \
            * ( label_replace(count(slurm_job_core_usage_total{{slurmjobid="{jobid}", {filter}}} / 1000) by (instance),"instance", "$1", "instance", "(.*):.*") / label_replace((count(node_cpu_seconds_total{{instance=~"({nodes_node_exporter})", mode="idle", {filter}}} / 1000) by (instance)), "instance", "$1", "instance", "(.*):.*") )'.format(
            nodes='|'.join(nodes),
            filter=prom.get_filter(),
            jobid=job.id_job,
            nodes_node_exporter=nodes_node_exporter,
        )
    return prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt(), step)


@login_required
@user_or_staff
def graph_power(request, username, job_id):
    uid = username_to_uid(username)
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except JobTable.DoesNotExist:
        return HttpResponseNotFound('Job not found')

    data = {'lines': []}
    for line in power(job, step=sanitize_step(request, minimum=prom.rate('redfish_exporter'))):
        compute_name = "{}".format(line['metric']['instance'])
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        data['lines'].append({
            'x': x,
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': compute_name,
            'hovertemplate': '%{y:.1f} W',
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
        for line in power(job, step=prom.rate('redfish_exporter')):
            # Instead of a proper integration, we just multiply the avg power by the time
            kw = (sum(line['y']) / len(line['y'])) / 1000  # compute the average power consumption
            kwhs.append(kw * hours)
        kwh = sum(kwhs)
        response['kwh'] = kwh
        if settings.ELECTRIC_CAR_RANGE_KM_PER_KWH:
            response['electric_car_range_km'] = kwh * float(settings.ELECTRIC_CAR_RANGE_KM_PER_KWH)
        if settings.ELECTRICITY_COST_PER_KWH:
            response['electricity_cost_dollar'] = kwh * float(settings.ELECTRICITY_COST_PER_KWH)
        if settings.COOLING_COST_PER_KWH:
            response['cooling_cost_dollar'] = kwh * float(settings.COOLING_COST_PER_KWH)
        if settings.CO2_KG_PER_MWH:
            response['co2_emissions_kg'] = kwh / 1000 * float(settings.CO2_KG_PER_MWH)
        if settings.AMORTIZATION_YEARS:
            response['amortization_years'] = float(settings.AMORTIZATION_YEARS)

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


class JobsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = JobTable.objects.all().order_by('-time_start')

        if self.request.query_params.get('status'):
            status = self.request.query_params.get('status').split(',')
            status_ints = []
            for item in status:
                for i in JobTable.state.field.get_choices():
                    if item == i[1]:
                        status_ints.append(i[0])
            queryset = queryset.filter(state__in=status_ints)

        if self.request.query_params.get('account'):
            account = self.request.query_params.get('account')
            # jobtable is not indexed by account, so we need to get assocs for this account, that one is indexed
            assocs = []
            for assoc in AssocTable.objects.filter(acct=account):
                assocs.append(assoc.id_assoc)
            queryset = queryset.filter(id_assoc__in=assocs)

            if user.is_staff is False:
                alloc_per_user = compute_allocations_by_user(user.get_username())
                for alloc in alloc_per_user:
                    if alloc['name'] == account:
                        # The user is a member of the account
                        queryset = queryset.filter(id_assoc__in=assocs)
                        break
                else:
                    # The user is not a member of the account, block access
                    queryset = JobTable.objects.none()

            else:
                # The user is a staff member
                queryset = queryset.filter(id_assoc__in=assocs)

        if user.is_staff:
            username = self.request.query_params.get('username')
            if username is not None:
                # Admin user can see all jobs of a specific user
                queryset = queryset.filter(id_user=username_to_uid(username))
            return queryset
        else:
            # Normal user can only see his own jobs and jobs of his accounts
            if self.request.query_params.get('account'):
                # Was previously filtered by account, so we can just return the queryset
                return queryset
            else:
                return queryset.filter(id_user=username_to_uid(user.get_username()))
