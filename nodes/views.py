from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from userportal.common import staff, Prometheus
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
    now = datetime.now()
    query = 'count(slurm_job_core_usage_total{{instance=~"{node}(:.*)", {filter}}}) by (account,user,slurmjobid)'.format(
        node=node,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, now - timedelta(days=2), now)

    users = {}
    for line in stats:
        start = min(line['x'])
        end = max(line['x'])
        cores = line['y'][0]
        user = line['metric']['user']
        jobid = line['metric']['slurmjobid']
        if(start == end):
            # skip short jobs
            continue

        if line['metric']['user'] not in users:
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
    return JsonResponse({'data': groups})
