from userportal.common import staff, Prometheus
from django.shortcuts import render
from django.http import JsonResponse
from slurm.models import JobTable, AssocTable
import time
import datetime
from django.conf import settings
import statistics
from django.db.models import Count

prom = Prometheus(settings.PROMETHEUS)


def get_start_end(request):
    start_string = request.GET.get('start', None)
    end_string = request.GET.get('end', None)

    try:
        if start_string:
            start = datetime.datetime.strptime(start_string, '%Y-%m-%d').timestamp()
        else:
            start = int(time.time()) - 604800 * 2
    except ValueError:
        start = int(time.time()) - 604800 * 2
    try:
        if end_string:
            end = datetime.datetime.strptime(end_string, '%Y-%m-%d').timestamp()
        else:
            end = int(time.time()) - 604800
    except ValueError:
        end = int(time.time()) - 604800

    return start, end


@staff
def index(request):
    return render(request, 'slurm/index.html')


@staff
def account_priority(request):
    context = {}
    account = request.GET.get('account', None)
    start, end = get_start_end(request)
    if account:
        context['account'] = account
    context['start'] = datetime.datetime.fromtimestamp(start)
    context['end'] = datetime.datetime.fromtimestamp(end)
    return render(request, 'slurm/account_priority.html', context)


@staff
def account_priority_json(request):
    account = request.GET.get('account', None)
    start, end = get_start_end(request)
    jobs = JobTable.objects.filter(time_start__gte=start, time_end__lte=end).order_by('-time_start').select_related('id_assoc')
    if account:
        jobs = jobs.filter(id_assoc__acct=account)

    partitions = set()
    accounts = set()
    for job in jobs:
        accounts.add(job.id_assoc.acct)
        partitions.add(job.partition)

    query_priority = 'slurm_account_levelfs{{account=~"{accounts}", {filter}}}'.format(
        accounts='|'.join(accounts),
        filter=prom.get_filter()
    )

    stats_priority = prom.query_prometheus_multiple(
        query=query_priority,
        start=datetime.datetime.fromtimestamp(start),
        end=datetime.datetime.fromtimestamp(end),
        step='1h')

    stats_by_account = {}
    for account_stats in stats_priority:
        stats_by_account[account_stats['metric']['account']] = (list(map(lambda x: int(x.timestamp()), account_stats['x'])), account_stats['y'])

    priorities_per_partition = {}
    for job in jobs:
        # get the priority when the job started
        if job.id_assoc.acct in stats_by_account:
            (x, y) = stats_by_account[job.id_assoc.acct]
            for i in x:
                if i > job.time_start:
                    job_priority = y[x.index(i)]

                    if job.partition in priorities_per_partition:
                        priorities_per_partition[job.partition].append(job_priority)
                    else:
                        priorities_per_partition[job.partition] = [job_priority]

                    break

    partitions_stats = []
    for partition in priorities_per_partition:
        partitions_stats.append({
            'name': partition,
            'mean': statistics.mean(priorities_per_partition[partition]),
            'median': statistics.median(priorities_per_partition[partition]),
            'max': max(priorities_per_partition[partition]),
            'min': min(priorities_per_partition[partition]),
            'count': len(priorities_per_partition[partition]),
        })
    return JsonResponse({'data': partitions_stats})


@staff
def job_length(request):
    context = {}
    account = request.GET.get('account', None)
    start, end = get_start_end(request)
    if account:
        context['account'] = account
    context['start'] = datetime.datetime.fromtimestamp(start)
    context['end'] = datetime.datetime.fromtimestamp(end)
    return render(request, 'slurm/job_length.html', context)


@staff
def job_length_json(request):
    account = request.GET.get('account', None)
    start, end = get_start_end(request)

    jobs = JobTable.objects.filter(
        time_start__gte=start,
        time_end__lte=end,
        state=JobTable.StatesJob.COMPLETE)\
        .order_by('-time_start').all()

    if account:
        jobs = jobs.filter(id_assoc__acct=account)

    ratios_per_partition = {}
    for job in jobs:
        actual_duration = (job.time_end - job.time_start) / 60
        predicted_duration = job.timelimit
        ratio = actual_duration / predicted_duration
        if job.partition in ratios_per_partition:
            ratios_per_partition[job.partition].append(ratio)
        else:
            ratios_per_partition[job.partition] = [ratio]

    stats_per_partition = []
    for partition in ratios_per_partition:
        stats_per_partition.append({
            'name': partition,
            'mean': statistics.mean(ratios_per_partition[partition]),
            'median': statistics.median(ratios_per_partition[partition]),
            'max': max(ratios_per_partition[partition]),
            'min': min(ratios_per_partition[partition]),
            'count': len(ratios_per_partition[partition]),
        })

    return JsonResponse({'data': stats_per_partition})


@staff
def job_timeout_json(request):
    account = request.GET.get('account', None)
    start, end = get_start_end(request)

    jobs_completed = JobTable.objects.filter(
        time_start__gte=start,
        time_end__lte=end,
        state=JobTable.StatesJob.COMPLETE)
    jobs_timeout = JobTable.objects.filter(
        time_start__gte=start,
        time_end__lte=end,
        state=JobTable.StatesJob.TIMEOUT)

    if account:
        jobs_completed = jobs_completed.filter(id_assoc__acct=account)
        jobs_timeout = jobs_timeout.filter(id_assoc__acct=account)

    jobs_states = (jobs_completed | jobs_timeout).values('state', 'partition').annotate(Count('job_db_inx'))
    data = []
    timeouts = {}
    completed = {}
    for job in jobs_states:
        if job['state'] == JobTable.StatesJob.TIMEOUT:
            timeouts[job['partition']] = job['job_db_inx__count']
        else:
            completed[job['partition']] = job['job_db_inx__count']

    for partitions in completed:
        data.append({
            'name': partitions,
            'timeout': timeouts.get(partitions, 0),
            'completed': completed[partitions],
            'ratio': timeouts.get(partitions, 0) / (completed[partitions] + timeouts.get(partitions, 0))
        })
    return JsonResponse({'data': data})


@staff
def account_list(request):
    accounts = AssocTable.objects.filter(deleted=False).values('acct').distinct()
    accounts_list = []
    for account in accounts:
        accounts_list.append(account['acct'])
    return JsonResponse({'accounts': accounts_list})
