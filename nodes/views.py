from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from userportal.common import staff, Prometheus
from userportal.common import anonymize as a
from datetime import datetime, timedelta


prom = Prometheus(settings.PROMETHEUS)
START = datetime.now() - timedelta(days=2)
END = datetime.now()


@login_required
@staff
def index(request):
    context = {}
    # slice of nodes to show in the table
    start = request.GET.get('start', 0)
    end = request.GET.get('end', 100)

    query = 'slurm_node_state_info{{ {filter} }}'.format(
        filter=prom.get_filter()
    )
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=1), datetime.now())
    nodes = []
    for line in stats:
        nodes.append(line['metric']['node'])

    # pagination
    nodes = nodes[start:end]

    query_cpu = 'sum(rate(node_cpu_seconds_total{{ {hostname_label}=~"({nodes})(:.*)", mode!="idle", {filter} }}[1m])) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        filter=prom.get_filter())

    node_stats = {}

    stats_cpu = prom.query_prometheus_multiple(query_cpu, datetime.now() - timedelta(hours=1), datetime.now(), step="1m")
    for cpu in stats_cpu:
        node_name = cpu['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name] = {'cpu': cpu['y']}

    context['node_stats'] = node_stats

    return render(request, 'nodes/index.html', context)


@login_required
@staff
def node(request, node):
    context = {}
    context['node'] = node

    query_gpu = 'count(slurm_job_utilization_gpu{{{hostname_label}=~"{node}(:.*)", {filter}}})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats_gpu = prom.query_prometheus_multiple(query_gpu, START, END)
    context['gpu'] = len(stats_gpu) > 0

    return render(request, 'nodes/node.html', context)


def node_gantt(node, gpu=False):
    if gpu:
        query_alloc = 'count(slurm_job_utilization_gpu{{{hostname_label}=~"{node}(:.*)", {filter}}})'.format(
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter())
        query_used = 'count(slurm_job_utilization_gpu{{{hostname_label}=~"{node}(:.*)", {filter}}}) by (account,user,slurmjobid)'.format(
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter())
        unit = 'gpu'
    else:
        query_alloc = 'count(node_cpu_seconds_total{{{hostname_label}=~"{node}(:.*)", mode="idle", {filter}}})'.format(
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter())
        query_used = 'count(slurm_job_core_usage_total{{{hostname_label}=~"{node}(:.*)", {filter}}}) by (account,user,slurmjobid)'.format(
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter())
        unit = 'cores'

    stats_alloc = prom.query_prometheus_multiple(query_alloc, START, END)

    node_alloc = max(stats_alloc[0]['y'])
    stats_used = prom.query_prometheus_multiple(query_used, START, END)

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
        'maxUnit': node_alloc,
        'unit': unit,
        'maxHeight': len(stats_used) * 30,
    })


@login_required
@staff
def node_gantt_cpu(request, node):
    return node_gantt(node, gpu=False)


@login_required
@staff
def node_gantt_gpu(request, node):
    return node_gantt(node, gpu=True)
