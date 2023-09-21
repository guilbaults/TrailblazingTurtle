from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from userportal.common import staff, Prometheus
from userportal.common import anonymize as a
from datetime import datetime, timedelta


prom = Prometheus(settings.PROMETHEUS)


@login_required
@staff
def index(request):
    context = {}

    return render(request, 'nodes/index.html', context)


@login_required
@staff
def node(request, node):
    context = {}
    context['node'] = node
    return render(request, 'nodes/node.html', context)


@login_required
@staff
def node_gantt(request, node):
    start = datetime.now() - timedelta(days=2)
    end = datetime.now()

    query_cores = 'count(node_cpu_seconds_total{{{hostname_label}=~"{node}(:.*)", mode="idle", {filter}}})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats_cores = prom.query_prometheus_multiple(query_cores, start, end)

    node_cores = stats_cores[0]['y'][0]

    query_used = 'count(slurm_job_core_usage_total{{{hostname_label}=~"{node}(:.*)", {filter}}}) by (account,user,slurmjobid)'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, start, end)

    users = {}
    for line in stats_used:
        start = min(line['x'])
        end = max(line['x'])
        cores = line['y'][0]
        user = a(line['metric']['user'])
        jobid = line['metric']['slurmjobid']
        if start == end:
            # skip short jobs
            continue

        if user not in users:
            users[user] = []

        users[user].append({
            'label': '{jobid}'.format(jobid=jobid),
            'data': [{
                'timeRange': [start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')],
                'val': cores,
            }],
        })

    groups = []
    for user in users:
        groups.append({
            'group': user,
            'data': users[user],
        })
    return JsonResponse({
        'data': groups,
        'maxCores': node_cores,
        'maxHeight': len(stats_used) * 30,
    })
