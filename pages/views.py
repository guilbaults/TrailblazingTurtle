from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from userportal.common import Prometheus, query_time
from django.utils.translation import gettext as _
from datetime import datetime, timedelta
import statistics
import re

prom = Prometheus(settings.PROMETHEUS)


def index(request):
    context = {}
    return render(request, 'pages/index.html', context)


def filesystem(request):
    context = {}
    context['fs'] = settings.LUSTRE_FS_NAMES
    return render(request, 'pages/filesystems.html', context)


def logins(request):
    context = {}
    context['logins'] = settings.LOGINS.keys()
    return render(request, 'pages/logins.html', context)


def dtns(request):
    context = {}
    context['dtns'] = settings.DTNS.keys()
    return render(request, 'pages/dtns.html', context)


def sheduler(request):
    context = {}
    return render(request, 'pages/scheduler.html', context)


def software(request):
    context = {}
    return render(request, 'pages/software.html', context)


def graph_lustre_mdt(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})
    timing = query_time(request)

    query = 'sum(lustre:metadata:rate3m{{fs="{}", {}}}) by (operation) !=0'.format(fs, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, timing[0], step=timing[1])

    data = []
    for line in stats:
        operation = line['metric']['operation']
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{}'.format(operation)
        })

    layout = {
        'yaxis': {
            'title': _('IOPS'),
        },
        'showlegend': False,
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }
    return JsonResponse({'data': data, 'layout': layout})


def graph_lustre_ost(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})
    timing = query_time(request)

    data = []
    for i in ['read', 'write']:
        query = 'lustre:{}_bytes:rate3m{{fs="{}", {}}}'.format(i, fs, prom.get_filter())
        stats = prom.query_prometheus_multiple(query, timing[0], step=timing[1])
        for line in stats:
            if i == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': '{}'.format(i)
            })

    layout = {
        'yaxis': {
            'ticksuffix': 'B/s',
            'tickformat': '~s',
            'title': _('Bandwidth'),
        },
        'showlegend': True,
        'legend': {
            'x': 0,
            'y': 1,
            'xanchor': 'right',
        },
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }
    return JsonResponse({'data': data, 'layout': layout})


def graph_login_cpu(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    timing = query_time(request)

    core_count_query = 'count(node_cpu_seconds_total{{mode="system",instance=~"{login}(:.*)?", {filter} }})'.format(
        login=login,
        filter=prom.get_filter(),
    )
    core_count = max(prom.query_prometheus(core_count_query, timing[0], step=timing[1])[1])
    data = []
    query = 'sum by (mode)(rate(node_cpu_seconds_total{{mode=~"system|user|iowait",instance=~"{login}(:.*)?", {filter} }}[{step}s]))'.format(
        login=login,
        filter=prom.get_filter(),
        step=timing[1],
    )
    stats = prom.query_prometheus_multiple(query, timing[0], step=timing[1])

    for line in stats:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{}'.format(line['metric']['mode']),
        })

    layout = {
        'yaxis': {
            'title': _('Cores'),
            'range': [0, core_count],
        },
        'showlegend': True,
        'legend': {
            'x': 0,
            'y': 1,
            'xanchor': 'right',
        },
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }

    return JsonResponse({'data': data, 'layout': layout})


def graph_login_memory(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    timing = query_time(request)

    total_mem_query = 'node_memory_MemTotal_bytes{{instance=~"{login}(:.*)?", {filter} }}'.format(
        login=login,
        filter=prom.get_filter(),
    )
    total_mem = max(prom.query_prometheus(total_mem_query, timing[0], step=timing[1])[1])
    data = []
    query = 'node_memory_MemTotal_bytes{{instance=~"{login}(:.*)?", {filter} }} - node_memory_MemFree_bytes{{instance=~"{login}(:.*)?", {filter} }} - node_memory_Buffers_bytes{{instance=~"{login}(:.*)?", {filter} }} - node_memory_Cached_bytes{{instance=~"{login}(:.*)?", {filter} }} - node_memory_Slab_bytes{{instance=~"{login}(:.*)?", {filter} }} - node_memory_PageTables_bytes{{instance=~"{login}(:.*)?", {filter} }} - node_memory_SwapCached_bytes{{instance=~"{login}(:.*)?", {filter} }}'.format(
        login=login,
        filter=prom.get_filter(),
    )
    stats = prom.query_prometheus(query, timing[0], step=timing[1])
    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats[0])),
        'y': stats[1],
        'type': 'scatter',
        'fill': 'tozeroy',
    })

    layout = {
        'yaxis': {
            'title': _('Memory'),
            'ticksuffix': 'B',
            'tickformat': '~s',
            'range': [0, total_mem],
        },
        'showlegend': False,
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }

    return JsonResponse({'data': data, 'layout': layout})


def graph_login_load(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    timing = query_time(request)
    data = []

    query = 'node_load1{{instance=~"{login}(:.*)?", {filter} }}'.format(
        login=login,
        filter=prom.get_filter(),
    )
    stats = prom.query_prometheus(query, timing[0], step=timing[1])
    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats[0])),
        'y': stats[1],
        'type': 'scatter',
        'fill': 'tozeroy',
    })

    layout = {
        'yaxis': {
            'title': _('Load'),
        },
        'showlegend': False,
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }

    return JsonResponse({'data': data, 'layout': layout})


def graph_login_network(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})

    device = settings.LOGINS[login]['network_interface']
    return graph_network(request, login, device)


def graph_dtn_network(request, dtn):
    if dtn not in settings.DTNS.keys():
        return JsonResponse({'error': 'Unknown dtn node'})

    device = settings.DTNS[dtn]['network_interface']
    return graph_network(request, dtn, device)


def graph_network(request, node, device):
    timing = query_time(request)
    data = []
    query_rx = 'rate(node_network_receive_bytes_total{{instance=~"{node}(:.*)?", device="{device}", {filter} }}[{step}s]) * 8'.format(
        node=node,
        filter=prom.get_filter(),
        device=device,
        step=timing[1],
    )
    stats_rx = prom.query_prometheus(query_rx, timing[0], step=timing[1])

    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_rx[0])),
        'y': [-x for x in stats_rx[1]],
        'type': 'scatter',
        'fill': 'tozeroy',
        'name': '{}'.format('Receive'),
    })

    query_tx = 'rate(node_network_transmit_bytes_total{{instance=~"{node}(:.*)?", device="{device}", {filter} }}[{step}s]) * 8'.format(
        node=node,
        filter=prom.get_filter(),
        device=device,
        step=timing[1],
    )
    stats_tx = prom.query_prometheus(query_tx, timing[0], step=timing[1])

    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_tx[0])),
        'y': stats_tx[1],
        'type': 'scatter',
        'fill': 'tozeroy',
        'name': '{}'.format('Transmit'),
    })

    layout = {
        'yaxis': {
            'title': _('Bandwidth'),
            'ticksuffix': 'b/s',
            'tickformat': '~s',
        },
        'showlegend': True,
        'legend': {
            'x': 0,
            'y': 1,
            'xanchor': 'right',
        },
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }

    return JsonResponse({'data': data, 'layout': layout})


def graph_scheduler_cpu(request):
    return graph_scheduler_cpu_gpu(request, 'cpu')


def graph_scheduler_gpu(request):
    return graph_scheduler_cpu_gpu(request, 'gpu')


def graph_scheduler_cpu_gpu(request, res_type='cpu'):
    timing = query_time(request)
    data = []
    if res_type == 'cpu':
        query_used = 'slurm_job:used_core:sum{{ {filter} }}'.format(
            filter=prom.get_filter(),
        )
    else:
        query_used = 'slurm_job:used_gpu:sum{{ {filter} }}'.format(
            filter=prom.get_filter(),
        )

    stats_used = prom.query_prometheus(query_used, timing[0], step=timing[1])
    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
        'y': stats_used[1],
        'type': 'scatter',
        'name': _('Used'),
    })

    query_alloc = 'slurm_{res_type}s_alloc{{ {filter} }}'.format(
        res_type=res_type,
        filter=prom.get_filter(),
    )
    stats_alloc = prom.query_prometheus(query_alloc, timing[0], step=timing[1])
    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
        'y': stats_alloc[1],
        'type': 'scatter',
        'name': _('Allocated'),
    })

    query_alloc = 'slurm_{res_type}s_alloc{{ {filter} }} + slurm_{res_type}s_idle{{ {filter} }}'.format(
        res_type=res_type,
        filter=prom.get_filter(),
    )
    stats_alloc = prom.query_prometheus(query_alloc, timing[0], step=timing[1])
    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
        'y': stats_alloc[1],
        'type': 'scatter',
        'name': _('Usable'),
    })

    if res_type == 'gpu':
        query_non_idle = 'sum(slurm_job:non_idle_gpu:sum_user_account{{ {filter} }})'.format(
            filter=prom.get_filter(),
        )
        stats_non_idle = prom.query_prometheus(query_non_idle, timing[0], step=timing[1])
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_non_idle[0])),
            'y': stats_non_idle[1],
            'type': 'scatter',
            'name': _('Active GPUs'),
        })

    query_total = 'slurm_{res_type}s_total{{ {filter} }}'.format(
        res_type=res_type,
        filter=prom.get_filter(),
    )
    stats_total = prom.query_prometheus(query_total, timing[0], step=timing[1])
    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_total[0])),
        'y': stats_total[1],
        'type': 'scatter',
        'name': _('Total'),
    })

    layout = {
        'yaxis': {
            'range': [0, max(stats_total[1])],
        },
        'showlegend': True,
        'margin': {
            'l': 70,
            'r': 0,
            'b': 50,
            't': 0,
            'pad': 0
        },
        'height': 300,
    }

    if res_type == 'gpu':
        layout['yaxis']['title'] = _('GPUs')
    else:
        layout['yaxis']['title'] = _('Cores')

    return JsonResponse({'data': data, 'layout': layout})


def graph_software_processes(request):
    query_str = 'sum(deriv(slurm_job_process_usage_total{{ {} }}[1m]) > 0) by (exe)'
    return graph_software(query_str, settings.SOFTWARE_REGEX)


def graph_software_stack(request):
    query_str = 'sum(deriv(slurm_job_process_usage_total{{ {} }}[1m]) > 0) by (exe)'
    return graph_software(query_str, settings.SOFTWARE_STACK_REGEX, extract_path=True)


def graph_software(query_str, software_regexes, extract_path=False):
    query = query_str.format(prom.get_filter())
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), step="5m")

    query_used = 'slurm_job:used_core:sum{{ {} }}'.format(prom.get_filter())
    stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), step="5m")

    values = []
    labels = []
    unidentified = 0
    accounted = 0
    software = {}

    for line in stats:
        value = statistics.median(line['y'])
        try:
            bin = line['metric']['exe']
        except KeyError:
            # Somehow the metric is missing the exe label
            continue
        for regex, name in software_regexes:
            if re.match(regex, bin):
                if name in software:
                    software[name] += value
                else:
                    software[name] = value
                accounted += value
                break
        else:
            if extract_path:
                name = "Stored in /{}".format(bin.split('/')[1])
                if name in software:
                    software[name] += value
                else:
                    software[name] = value
            else:
                unidentified += value
            accounted += value

    for key in software.keys():
        labels.append(key)
        values.append(software[key])

    if unidentified > 0:
        # Software that are not in the list of known regexes
        labels.append(_('Unidentified'))
        values.append(unidentified)

    used = statistics.median(stats_used[1])
    if used > accounted:
        labels.append(_('Unaccounted'))
        values.append(used - accounted)

    data = {'data': [{
        'values': values,
        'labels': labels,
        'type': 'pie',
        'texttemplate': '%{label}: %{value:.0f}',
    }]}

    data['layout'] = {
    }
    return JsonResponse(data)
