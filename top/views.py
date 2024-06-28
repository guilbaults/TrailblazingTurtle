from django.shortcuts import render
from django.http import JsonResponse
from userportal.common import staff, Prometheus, uid_to_username
from userportal.common import anonymize as a
from slurm.models import JobTable
from notes.models import Note
from django.conf import settings
from django.contrib.auth.decorators import login_required
import time
from datetime import datetime, timedelta
from django.utils.translation import gettext as _

prom = Prometheus(settings.PROMETHEUS)


@login_required
@staff
def index(request):
    return render(request, 'top/index.html')


def metrics_to_user(metrics):
    users_metrics = {}
    for line in metrics:
        users_metrics[(line['metric']['user'], line['metric']['account'])] = float(line['value'][1])
    return users_metrics


def metrics_to_job(metrics):
    jobs_metrics = {}
    for line in metrics:
        jobs_metrics[line['metric']['slurmjobid']] = float(line['value'][1])
    return jobs_metrics


def stats_for_users(users=None):
    if users is None:
        # get the top 100 and use the same list for all the other queries
        query_cpu = 'topk(100, sum(slurm_job:allocated_core:count_user_account{{ {filter} }}) by (user, account))'.format(
            filter=prom.get_filter())
        stats_cpu = prom.query_last(query_cpu)
        users = []
        for line in stats_cpu:
            users.append(line['metric']['user'])
    else:
        # use the list of users as filter
        query_cpu = 'sum(slurm_job:allocated_core:count_user_account{{ user=~"{users}", {filter} }}) by (user, account)'.format(
            users='|'.join(users),
            filter=prom.get_filter())
        stats_cpu = prom.query_last(query_cpu)
    stats_cpu_asked = metrics_to_user(stats_cpu)

    query_cpu_used = 'sum(slurm_job:used_core:sum_user_account{{user=~"{users}", {filter} }}) by (user, account)'.format(
        users='|'.join(users),
        filter=prom.get_filter())
    stats_cpu_used = metrics_to_user(prom.query_last(query_cpu_used))

    query_mem_asked = 'sum(slurm_job:allocated_memory:sum_user_account{{user=~"{users}", {filter}}}) by (user, account)'.format(
        users='|'.join(users),
        filter=prom.get_filter())
    stats_mem_asked = metrics_to_user(prom.query_last(query_mem_asked))
    query_mem_max = 'sum(slurm_job:max_memory:sum_user_account{{user=~"{users}", {filter}}}) by (user, account)'.format(
        users='|'.join(users),
        filter=prom.get_filter())
    stats_mem_max = metrics_to_user(prom.query_last(query_mem_max))
    return (stats_cpu_asked, stats_cpu_used, stats_mem_asked, stats_mem_max)


@login_required
@staff
def compute(request):
    context = {}
    stats_cpu_asked, stats_cpu_used, stats_mem_asked, stats_mem_max = stats_for_users(users=None)

    lines = stats_cpu_asked.keys()
    users = [x[0] for x in lines]

    # get notes
    notes = Note.objects.filter(username__in=users).filter(deleted_at=None)
    note_per_user = set()
    for note in notes:
        note_per_user.add(note.username)

    context['cpu_users'] = []
    for line in lines:
        try:
            reasonable_mem = stats_cpu_asked[line] * settings.NORMAL_MEM_BY_CORE * 1.1
            user = line[0]
            account = line[1]

            stats = {
                'user': user,
                'account': account,
                'cpu_asked': stats_cpu_asked[line],
                'cpu_used': stats_cpu_used[line],
                'cpu_ratio': stats_cpu_used[line] / stats_cpu_asked[line],
                'mem_asked': stats_mem_asked[line],
                'mem_max': stats_mem_max[line],
                'mem_ratio': stats_mem_max[line] / stats_mem_asked[line],
                'note_flag': user in note_per_user,
            }
            waste_badges = []
            if stats_mem_asked[line] > reasonable_mem:
                # If the user ask for more memory than what's available per core on a standard node
                if stats['mem_ratio'] < 0.1:
                    waste_badges.append(('danger', _('Memory')))
                elif stats['mem_ratio'] < 0.5:
                    waste_badges.append(('warning', _('Memory')))
            else:
                # The user might be wasting memory, but this is fine since its probably cpu bound and fully use the node regardless
                # No other users could use the left-over memory in most cases since all cores are presumed to be used
                # The next check will ensure that all cores are used
                pass

            if stats['cpu_ratio'] < 0.75:
                waste_badges.append(('danger', _('Cores')))
            elif stats['cpu_ratio'] < 0.9:
                waste_badges.append(('warning', _('Cores')))

            stats['waste_badges'] = waste_badges
            context['cpu_users'].append(stats)
        except KeyError:
            pass

    return render(request, 'top/compute.html', context)


@login_required
@staff
def gpucompute(request):
    context = {}

    query_gpu = 'topk(100, sum(slurm_job:allocated_gpu:count_user_account{{ {filter} }}) by (user, account))'.format(
        filter=prom.get_filter())
    stats_gpu = prom.query_last(query_gpu)
    gpu_users = []
    for line in stats_gpu:
        gpu_users.append(line['metric']['user'])

    stats_gpu_asked = metrics_to_user(stats_gpu)

    query_gpu_util = 'sum(slurm_job:used_gpu:sum_user_account{{user=~"{users}", {filter} }}) by (user, account)'.format(
        users='|'.join(gpu_users),
        filter=prom.get_filter())
    stats_gpu_util = metrics_to_user(prom.query_last(query_gpu_util))

    query_gpu_used = 'sum(slurm_job:non_idle_gpu:sum_user_account{{user=~"{users}", {filter}}}) by (user, account)'.format(
        users='|'.join(gpu_users),
        filter=prom.get_filter())
    stats_gpu_used = metrics_to_user(prom.query_last(query_gpu_used))

    # grab the cores, memory for each user
    users = [x[0] for x in stats_gpu_asked.keys()]
    stats_cpu_asked, stats_cpu_used, stats_mem_asked, stats_mem_max = stats_for_users(users=users)

    # get notes
    notes = Note.objects.filter(username__in=users).filter(deleted_at=None)
    note_per_user = set()
    for note in notes:
        note_per_user.add(note.username)

    context['gpu_users'] = []
    for line in stats_gpu:
        try:
            user = line['metric']['user']
            account = line['metric']['account']
            identifier = (user, account)
            if identifier not in stats_gpu_used:
                # User is not using any GPU
                stats_gpu_used[identifier] = 0

            reasonable_mem = stats_gpu_asked[identifier] * settings.NORMAL_MEM_BY_GPU * 1.1
            reasonable_cores = stats_gpu_asked[identifier] * settings.NORMAL_CORES_BY_GPU * 1.1

            stats = {
                'user': user,
                'account': account,
                'gpu_asked': stats_gpu_asked[identifier],
                'gpu_util': stats_gpu_util[identifier],
                'gpu_used': stats_gpu_used[identifier],
                'gpu_ratio': stats_gpu_util[identifier] / stats_gpu_asked[identifier],
                'cpu_asked': stats_cpu_asked[identifier],
                'cpu_used': stats_cpu_used[identifier],
                'cpu_ratio': stats_cpu_used[identifier] / stats_cpu_asked[identifier],
                'mem_asked': stats_mem_asked[identifier],
                'mem_max': stats_mem_max[identifier],
                'mem_ratio': stats_mem_max[identifier] / stats_mem_asked[identifier],
                'reasonable_mem': stats_mem_asked[identifier] < reasonable_mem,
                'reasonable_cores': stats_cpu_asked[identifier] < reasonable_cores,
                'note_flag': user in note_per_user,
            }
            waste_badges = []
            if stats_mem_asked[identifier] > reasonable_mem:
                # Using more memory than the fair share per GPU
                if stats['mem_ratio'] < 0.1:
                    waste_badges.append(('danger', _('Memory')))
                elif stats['mem_ratio'] < 0.5:
                    waste_badges.append(('warning', _('Memory')))
            if stats_cpu_asked[identifier] > reasonable_cores:
                # Using more cores than the fair share per GPU
                if stats['cpu_ratio'] < 0.75:
                    waste_badges.append(('danger', _('Cores')))
                elif stats['cpu_ratio'] < 0.9:
                    waste_badges.append(('warning', _('Cores')))
            if stats['gpu_used'] == float(0):
                waste_badges.append(('danger', _('GPU ares totally unused')))
            elif stats['gpu_ratio'] < 0.1:
                waste_badges.append(('danger', _('GPUs')))
            elif stats['gpu_ratio'] < 0.2:
                waste_badges.append(('warning', _('GPUs')))

            stats['waste_badges'] = waste_badges
            context['gpu_users'].append(stats)
        except KeyError:
            pass
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
    by_users = {}
    for job in jobs_running:
        try:
            job_id = str(job.id_job)
            user = uid_to_username(job.id_user)
            account = job.account

            if (user, account) not in by_users:
                by_users[(user, account)] = {
                    'cpu_asked': stats_cpu_asked[job_id],
                    'cpu_used': stats_cpu_used[job_id],
                    'mem_asked': stats_mem_asked[job_id],
                    'mem_max': stats_mem_max[job_id],
                }
            else:
                by_users[(user, account)]['cpu_asked'] += stats_cpu_asked[job_id]
                by_users[(user, account)]['cpu_used'] += stats_cpu_used[job_id]
                by_users[(user, account)]['mem_asked'] += stats_mem_asked[job_id]
                by_users[(user, account)]['mem_max'] += stats_mem_max[job_id]
        except KeyError:
            pass

    # gather all usernames
    users = set()
    for job in jobs_running:
        users.add(uid_to_username(job.id_user))

    # get notes per user
    notes = Note.objects.filter(username__in=users).filter(deleted_at=None)
    note_per_user = set()
    for note in notes:
        note_per_user.add(note.username)

    # gather all jobid
    jobids = set()
    for job in jobs_running:
        jobids.add(job.id_job)

    notes = Note.objects.filter(job_id__in=jobids).filter(deleted_at=None)
    note_per_jobid = set()
    for note in notes:
        note_per_jobid.add(note.job_id)

    # if user has a note, add a flag to the user
    for job in context['jobs']:
        if job['user'] in note_per_user:
            job['user_flag'] = True
        if job['job_id'] in note_per_jobid:
            job['job_flag'] = True

    # convert dict to list
    context['by_users'] = []
    for (user, account), stats in by_users.items():
        if user in note_per_user:
            stats['user_flag'] = True
        stats['user'] = user
        stats['account'] = account
        stats['cpu_ratio'] = stats['cpu_used'] / stats['cpu_asked']
        stats['mem_ratio'] = stats['mem_max'] / stats['mem_asked']
        stats['min_ratio'] = min(stats['cpu_ratio'], stats['mem_ratio'])

        waste_badges = []
        if stats['mem_ratio'] < 0.1:
            waste_badges.append(('danger', _('Memory')))
        elif stats['mem_ratio'] < 0.5:
            waste_badges.append(('warning', _('Memory')))
        if stats['cpu_ratio'] < 0.75:
            waste_badges.append(('danger', _('Cores')))
        elif stats['cpu_ratio'] < 0.9:
            waste_badges.append(('warning', _('Cores')))
        stats['waste_badges'] = waste_badges

        context['by_users'].append(stats)

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
    query = 'topk(20, lustre:metadata:rate3m_user{{fs="{fs}", user!="root", {filter}}})'.format(
        fs=fs,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=24), datetime.now())
    data = []
    for line in stats:
        try:
            user = a(line['metric']['user'])
        except KeyError:
            user = 'others'

        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': user
        })

    layout = {
        'yaxis': {
            'ticksuffix': _('IOPS')
        }
    }
    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
def graph_lustre_ost(request, fs):
    data = []
    for rw in ['read', 'write']:
        query = 'topk(20, lustre:{rw}_bytes:rate3m_user{{fs="{fs}", user!="root", {filter}}})/1024/1024'.format(
            rw=rw,
            fs=fs,
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=24), datetime.now())

        for line in stats:
            try:
                user = a(line['metric']['user'])
            except KeyError:
                user = 'others'

            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if rw == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]

            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(rw, user)
            })

    layout = {
        'yaxis': {
            'ticksuffix': _('MiB/s')
        }
    }
    return JsonResponse({'data': data, 'layout': layout})
