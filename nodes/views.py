from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from userportal.common import staff, Prometheus, parse_start_end
from userportal.common import anonymize as a
from datetime import datetime, timedelta
from django.utils.translation import gettext as _
from jobstats.views import GPU_MEMORY, GPU_SHORT_NAME, GPU_IDLE_POWER, GPU_FULL_POWER
from slurm.models import EventTable


prom = Prometheus(settings.PROMETHEUS)
START = datetime.now() - timedelta(days=2)
END = datetime.now()


def cpu_count(node):
    # return the number of cpu cores on a node
    query = 'count(node_cpu_seconds_total{{ {hostname_label}=~"{node}(:.*)", mode="idle", {filter} }}) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, START, END, step="5m")
    return int(max(stats[0]['y']))


def memory(node):
    query = 'node_memory_MemTotal_bytes{{ {hostname_label}=~"{node}(:.*)", {filter} }}'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, START, END, step="5m")
    return int(max(stats[0]['y']))


@login_required
@staff
def index(request):
    context = {}
    # slice of nodes to show in the table
    start = int(request.GET.get('start', 0))
    step = 100
    end = int(request.GET.get('end', step))

    query = 'slurm_node_state_info{{ {filter} }}'.format(
        filter=prom.get_filter()
    )
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(minutes=10), datetime.now())
    nodes = []
    node_states = {}
    for line in stats:
        name = line['metric']['node']+settings.HOSTNAME_DOMAIN
        nodes.append(name)
        node_states[name] = {'state': line['metric']['state']}

    # pagination
    nodes = nodes[start:end]
    node_stats = {}

    query_cpu_count = 'count(node_cpu_seconds_total{{ {hostname_label}=~"({nodes})(:.*)", mode="idle", {filter} }}) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        filter=prom.get_filter())

    stats_cpu_count = prom.query_prometheus_multiple(query_cpu_count, datetime.now() - timedelta(hours=1), datetime.now(), step="5m")
    for cpu in stats_cpu_count:
        node_name = cpu['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name] = {
            'name': node_name,
            'cpu_count': max(cpu['y']),
            'state': node_states[node_name]['state'],
        }

    query_cpu = 'sum(rate(node_cpu_seconds_total{{ {hostname_label}=~"({nodes})(:.*)", mode!="idle", {filter} }}[1m])) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        filter=prom.get_filter())
    stats_cpu = prom.query_prometheus_multiple(query_cpu, datetime.now() - timedelta(hours=1), datetime.now(), step="1m")

    for cpu in stats_cpu:
        node_name = cpu['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name]['cpu_used'] = cpu['y']
        node_stats[node_name]['cpu_used_avg'] = sum(cpu['y']) / len(cpu['y'])

    query_memory_installed = 'max(node_memory_MemTotal_bytes{{ {hostname_label}=~"({nodes})(:.*)", {filter} }}) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        filter=prom.get_filter())
    stats_memory_installed = prom.query_prometheus_multiple(query_memory_installed, datetime.now() - timedelta(hours=1), datetime.now(), step="10m")
    for memory in stats_memory_installed:
        node_name = memory['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name]['mem_installed'] = max(memory['y'])

    query_memory_used = 'max(node_memory_MemTotal_bytes{{ {hostname_label}=~"({nodes})(:.*)", {filter} }} \
        - node_memory_MemFree_bytes{{ {hostname_label}=~"({nodes})(:.*)", {filter} }} \
        - node_memory_Buffers_bytes{{ {hostname_label}=~"({nodes})(:.*)", {filter} }} \
        - node_memory_Cached_bytes{{ {hostname_label}=~"({nodes})(:.*)", {filter} }}) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        filter=prom.get_filter())

    stats_memory_used = prom.query_prometheus_multiple(query_memory_used, datetime.now() - timedelta(hours=1), datetime.now(), step="1m")
    for memory in stats_memory_used:
        node_name = memory['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name]['mem_used'] = memory['y']
        node_stats[node_name]['mem_used_avg'] = sum(memory['y']) / len(memory['y'])

    query_disk_installed = 'max(node_filesystem_size_bytes{{ {hostname_label}=~"({nodes})(:.*)", mountpoint="{localscratch}", {filter} }}) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        localscratch=settings.LOCALSCRATCH,
        filter=prom.get_filter())
    stats_disk_installed = prom.query_prometheus_multiple(query_disk_installed, datetime.now() - timedelta(hours=1), datetime.now(), step="10m")
    for disk in stats_disk_installed:
        node_name = disk['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name]['disk_installed'] = max(disk['y'])

    query_disk_used = 'max(node_filesystem_size_bytes{{ {hostname_label}=~"({nodes})(:.*)", mountpoint="{localscratch}", {filter} }} \
        - node_filesystem_free_bytes{{ {hostname_label}=~"({nodes})(:.*)", mountpoint="{localscratch}", {filter} }}) by ({hostname_label})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        nodes='|'.join(nodes),
        localscratch=settings.LOCALSCRATCH,
        filter=prom.get_filter())
    stats_disk_used = prom.query_prometheus_multiple(query_disk_used, datetime.now() - timedelta(hours=1), datetime.now(), step="1m")
    for disk in stats_disk_used:
        node_name = disk['metric'][settings.PROM_NODE_HOSTNAME_LABEL].split(':')[0]
        node_stats[node_name]['disk_used'] = disk['y']
        node_stats[node_name]['disk_used_avg'] = sum(disk['y']) / len(disk['y'])

    context['node_stats'] = list(node_stats.values())
    context['next_start'] = end
    context['next_end'] = end + step

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

    context['node_events'] = []
    try:
        start = START.timestamp()
        end = END.timestamp()

        started = EventTable.objects\
            .filter(node_name=node)\
            .filter(time_start__gte=start)\
            .filter(time_start__lte=end).all()

        ended = EventTable.objects\
            .filter(node_name=node)\
            .filter(time_end__gte=start)\
            .filter(time_end__lte=end).all()

        context['node_events'] = started | ended
    except IndexError:
        pass

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
    events = []
    count = 0
    for event in node_state(node):
        events.append({
            'label': '{} {}'.format(event[2], count),
            'data': [{
                'timeRange': [event[0].strftime('%Y-%m-%d %H:%M:%S'), event[1].strftime('%Y-%m-%d %H:%M:%S')],
                'val': 0,
            }],
        })
        count += 1
    groups.append({
        'group': '_states',
        'data': events,
    })

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


def node_state(node):
    events = []
    for state in ['down', 'drained', 'draining', 'fail']:
        query = 'count(slurm_node_state_info{{node="{node}", state=~"{state}", {filter}}}) or on() vector(0)'.format(
            node=node,
            state=state,
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(query, START, END)
        for line in stats:
            # zip together the x and y values
            data = list(zip(line['x'], line['y']))
            # only trigger a event if the state moves from 0 to 1
            trigger = False
            starts = []
            ends = []
            for item in data:
                if int(item[1]) == 1:
                    if trigger:
                        # already triggered
                        continue
                    else:
                        # up transition
                        trigger = True
                        starts.append(item[0])
                else:
                    if trigger:
                        # down transition
                        ends.append(item[0])
                        trigger = False
            if len(starts) > len(ends):
                # still in state
                ends.append(datetime.now())
            # zip together the start and end times
            if len(starts) > 0:
                for event in list(zip(starts, ends, [state] * len(starts))):
                    events.append(event)
    return events


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_disk_used(request, node):
    query_disk = '(node_filesystem_size_bytes{{{hostname_label}=~"{node}(:.*)", {filter}}} - node_filesystem_avail_bytes{{{hostname_label}=~"{node}(:.*)", {filter}}})/(1000*1000*1000)'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats_disk = prom.query_prometheus_multiple(query_disk, request.start, request.end, step=request.step)

    data = []
    for line in stats_disk:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': line['metric']['mountpoint'],
            'hovertemplate': '%{y:.1f} GB',
        })

    layout = {
        'yaxis': {
            'ticksuffix': ' GB',
            'title': _('Disk'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_cpu_jobstats(request, node):
    query = 'sum(rate(slurm_job_core_usage_total{{{hostname_label}=~"{node}(:.*)", {filter}}}[{step}s]) / 1000000000) by (user, slurmjobid)'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter(),
        step=prom.rate('slurm-job-exporter'))
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    for line in stats:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': '{} {}'.format(a(line['metric']['user']), line['metric']['slurmjobid']),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'title': _('Cores'),
            'range': [0, cpu_count(node)],
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_cpu_node(request, node):
    query = 'sum by (mode)(irate(node_cpu_seconds_total{{mode!="idle",{hostname_label}=~"{node}(:.*)",{filter}}}[{step}s]))'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter(),
        step=prom.rate('node_exporter'))
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    for line in stats:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': line['metric']['mode'],
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'title': _('Cores'),
            'range': [0, cpu_count(node)],
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_memory_jobstats(request, node):
    query = '(sum(slurm_job_memory_usage{{{hostname_label}=~"{node}(:.*)", {filter}}}) by (user, slurmjobid))/(1024*1024*1024)'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    for line in stats:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': '{} {}'.format(a(line['metric']['user']), line['metric']['slurmjobid']),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'title': _('Memory'),
            'ticksuffix': 'GiB',
            'range': [0, memory(node) / (1024 * 1024 * 1024)],
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_memory_node(request, node):
    data = []
    query_apps = '(node_memory_MemTotal_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}} - \
        node_memory_MemFree_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}} - \
        node_memory_Buffers_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}} - \
        node_memory_Cached_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}} - \
        node_memory_Slab_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}} - \
        node_memory_PageTables_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}} - \
        node_memory_SwapCached_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}})/(1024*1024*1024)'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats_apps = prom.query_prometheus_multiple(query_apps, request.start, request.end, step=request.step)
    for line in stats_apps:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': 'Apps',
            'hovertemplate': '%{y:.1f}',
        })

    for memory_type in ['PageTables', 'SwapCached', 'Slab', 'Cached', 'Buffers', 'HardwareCorrupted']:
        query = 'node_memory_{memory_type}_bytes{{{hostname_label}=~"{node}(:.*)",{filter}}}/(1024*1024*1024)'.format(
            memory_type=memory_type,
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)
        for line in stats:
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': line['y'],
                'type': 'scatter',
                'stackgroup': 'one',
                'name': memory_type,
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'title': _('Memory'),
            'ticksuffix': 'GiB',
            'range': [0, memory(node) / (1024 * 1024 * 1024)],
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_ethernet_bdw(request, node):
    data = []

    for direction in ['receive', 'transmit']:
        query = 'rate(node_network_{direction}_bytes_total{{device!~"ib.*|lo", {hostname_label}=~"{node}(:.*)", {filter}}}[{step}s]) * 8 / (1000*1000)'.format(
            direction=direction,
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter(),
            step=prom.rate('node_exporter'))
        stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)
        for line in stats:
            if direction == 'receive':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, line['metric']['device']),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': ' Mb/s',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_infiniband_bdw(request, node):
    data = []
    for direction in ['received', 'transmitted']:
        query = 'rate(node_infiniband_port_data_{direction}_bytes_total{{{hostname_label}=~"{node}(:.*)", {filter}}}[{step}s]) * 8 / (1000*1000*1000)'.format(
            direction=direction,
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter(),
            step=prom.rate('node_exporter'))
        stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)
        for line in stats:
            if direction == 'received':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': y,
                'type': 'scatter',
                'name': direction,
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': ' Gb/s',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_disk_iops(request, node):
    data = []
    for direction in ['reads', 'writes']:
        query = 'rate(node_disk_{direction}_completed_total{{{hostname_label}=~"{node}(:.*)",device=~"nvme.n.|sd.|vd.", {filter}}}[{step}s])'.format(
            direction=direction,
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter(),
            step=prom.rate('node_exporter'))
        stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)
        for line in stats:
            y = line['y']
            if direction == 'reads':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, line['metric']['device']),
                'hovertemplate': '%{y:.1f} IOPS',
            })

    layout = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_disk_bdw(request, node):
    data = []
    for direction in ['read', 'written']:
        query = 'rate(node_disk_{direction}_bytes_total{{{hostname_label}=~"{node}(:.*)",device=~"nvme.n.|sd.|vd.", {filter}}}[{step}s])'.format(
            direction=direction,
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter(),
            step=prom.rate('node_exporter'))
        stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)
        for line in stats:
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, line['metric']['device']),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': 'B/s',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_gpu_utilization(request, node):
    data = []
    queries = [
        ('slurm_job_utilization_gpu', _('SM Active')),
        ('slurm_job_sm_occupancy_gpu', _('SM Occupancy')),
        ('slurm_job_tensor_gpu', _('Tensor')),
        ('slurm_job_fp64_gpu', _('FP64')),
        ('slurm_job_fp32_gpu', _('FP32')),
        ('slurm_job_fp16_gpu', _('FP16')),
    ]

    for q in queries:
        query = '{query}{{{hostname_label}=~"{node}(:.*)", {filter}}}'.format(
            query=q[0],
            hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
            node=node,
            filter=prom.get_filter())
        stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

        for line in stats:
            name = '{t} {user} {jobid} GPU {gpuid}'.format(
                t=q[1],
                user=a(line['metric']['user']),
                jobid=line['metric']['slurmjobid'],
                gpuid=line['metric']['gpu'])
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': line['y'],
                'type': 'scatter',
                'name': name,
                'hovertemplate': '%{y:.1f}%',
            })
    layout = {
        'yaxis': {
            'ticksuffix': ' %',
            'range': [0, 100],
            'title': _('GPU Utilization'),
        }
    }
    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_gpu_memory(request, node):
    query = 'slurm_job_memory_usage_gpu{{{hostname_label}=~"{node}(:.*)", {filter}}} /(1024*1024*1024)'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    for line in stats:
        name = '{user} {jobid} GPU {gpuid} '.format(
            user=a(line['metric']['user']),
            jobid=line['metric']['slurmjobid'],
            gpuid=line['metric']['gpu'])
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f} GiB',
        })
    layout = {
        'yaxis': {
            'ticksuffix': ' GiB',
            'range': [0, GPU_MEMORY[line['metric']['gpu_type']]],
            'title': _('GPU Memory'),
        }
    }
    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(timedelta_start=timedelta(days=7))
def graph_gpu_power(request, node):
    query = 'slurm_job_power_gpu{{{hostname_label}=~"{node}(:.*)", {filter}}}/1000'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter())
    stats = prom.query_prometheus_multiple(query, request.start, request.end, step=request.step)

    data = []
    for line in stats:
        gpu_type = line['metric']['gpu_type']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        name = '{user} {jobid} GPU {gpuid}'.format(
            user=a(line['metric']['user']),
            jobid=line['metric']['slurmjobid'],
            gpuid=line['metric']['gpu'])
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': name,
            'hovertemplate': '%{y:.1f} W',
        })

    if len(stats) > 0:
        data.append({
            'x': x,
            'y': [GPU_IDLE_POWER[gpu_type] for x in y],
            'type': 'scatter',
            'name': '{} {}'.format(GPU_SHORT_NAME[gpu_type], _('Idle power')),
            'hovertemplate': '%{y:.1f} W',
        })

        layout = {
            'yaxis': {
                'ticksuffix': ' W',
                'range': [0, GPU_FULL_POWER[gpu_type]],
                'title': _('GPU Power'),
            }
        }
    return JsonResponse({'data': data, 'layout': layout})
