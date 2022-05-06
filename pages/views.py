from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from userportal.common import Prometheus
from datetime import datetime, timedelta

prom = Prometheus(settings.PROMETHEUS)


def index(request):
    context = {}
    return render(request, 'pages/index.html', context)


def filesystem(request):
    context = {}
    context['fs'] = settings.LUSTRE_FS_NAMES
    return render(request, 'pages/filesystem.html', context)


def logins(request):
    context = {}
    context['logins'] = settings.LOGINS.keys()
    return render(request, 'pages/logins.html', context)


def query_time(request):
    delta = request.GET.get('delta', '1h')

    if delta == '1w':
        start = datetime.now() - timedelta(weeks=1)
        step = '1h'
    elif delta == '1d':
        start = datetime.now() - timedelta(days=1)
        step = '15m'
    else:
        # default to 1 hour
        start = datetime.now() - timedelta(hours=1)
        step = '1m'

    return (start, step)


def graph_lustre_mdt(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})
    timing = query_time(request)

    query = 'sum(lustre:metadata:rate3m{{fs="{}", {}}}) by (operation) !=0'.format(fs, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, timing[0], step=timing[1])

    data = {'lines': []}
    for line in stats:
        operation = line['metric']['operation']
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{}'.format(operation)
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': ' IOPS'
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
    return JsonResponse(data)


def graph_lustre_ost(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})
    timing = query_time(request)

    data = {'lines': []}
    for i in ['read', 'write']:
        query = 'lustre:{}_bytes:rate3m{{fs="{}", {}}}'.format(i, fs, prom.get_filter())
        stats = prom.query_prometheus_multiple(query, timing[0], step=timing[1])
        for line in stats:
            data['lines'].append({
                'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
                'y': line['y'],
                'type': 'scatter',
                'name': '{}'.format(i)
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'B/s',
            'tickformat': '~s',
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
    return JsonResponse(data)


def graph_login_cpu(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    timing = query_time(request)

    core_count_query = 'count(node_cpu_seconds_total{{mode="system",instance=~"{login}:.*", {filter} }})'.format(
        login=login,
        filter=prom.get_filter(),
    )
    core_count = max(prom.query_prometheus(core_count_query, timing[0], step=timing[1])[1])
    data = {'lines': []}
    query = 'sum by (mode)(rate(node_cpu_seconds_total{{mode=~"system|user|iowait",instance=~"{login}:.*", {filter} }}[{step}]))'.format(
        login=login,
        filter=prom.get_filter(),
        step=timing[1],
    )
    stats = prom.query_prometheus_multiple(query, timing[0], step=timing[1])

    for line in stats:
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': '{}'.format(line['metric']['mode']),
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'Cores',
            'tickformat': '~s',
            'range': [0, core_count],
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

    return JsonResponse(data)


def graph_login_memory(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    timing = query_time(request)

    total_mem_query = 'node_memory_MemTotal_bytes{{instance=~"{login}:.*", {filter} }}'.format(
        login=login,
        filter=prom.get_filter(),
    )
    total_mem = max(prom.query_prometheus(total_mem_query, timing[0], step=timing[1])[1])
    data = {'lines': []}
    query = 'node_memory_MemTotal_bytes{{instance=~"{login}:.*", {filter} }} - node_memory_MemFree_bytes{{instance=~"{login}:.*", {filter} }} - node_memory_Buffers_bytes{{instance=~"{login}:.*", {filter} }} - node_memory_Cached_bytes{{instance=~"{login}:.*", {filter} }} - node_memory_Slab_bytes{{instance=~"{login}:.*", {filter} }} - node_memory_PageTables_bytes{{instance=~"{login}:.*", {filter} }} - node_memory_SwapCached_bytes{{instance=~"{login}:.*", {filter} }}'.format(
        login=login,
        filter=prom.get_filter(),
    )
    stats = prom.query_prometheus(query, timing[0], step=timing[1])
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats[0])),
        'y': stats[1],
        'type': 'scatter',
    })

    data['layout'] = {
        'yaxis': {
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

    return JsonResponse(data)


def graph_login_load(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    timing = query_time(request)
    data = {'lines': []}

    query = 'node_load1{{instance=~"{login}:.*", {filter} }}'.format(
        login=login,
        filter=prom.get_filter(),
    )
    stats = prom.query_prometheus(query, timing[0], step=timing[1])
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats[0])),
        'y': stats[1],
        'type': 'scatter',
    })

    data['layout'] = {
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

    return JsonResponse(data)


def graph_login_network(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    device = settings.LOGINS[login]['network_interface']
    timing = query_time(request)
    data = {'lines': []}
    query_rx = 'rate(node_network_receive_bytes_total{{instance=~"{login}:.*", device="{device}", {filter} }}[{step}]) * 8'.format(
        login=login,
        filter=prom.get_filter(),
        device=device,
        step=timing[1],
    )
    stats_rx = prom.query_prometheus(query_rx, timing[0], step=timing[1])

    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_rx[0])),
        'y': stats_rx[1],
        'type': 'scatter',
        'name': '{}'.format('Receive'),
    })

    query_tx = 'rate(node_network_transmit_bytes_total{{instance=~"{login}:.*", device="{device}", {filter} }}[{step}]) * 8'.format(
        login=login,
        filter=prom.get_filter(),
        device=device,
        step=timing[1],
    )
    stats_tx = prom.query_prometheus(query_tx, timing[0], step=timing[1])

    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_tx[0])),
        'y': stats_tx[1],
        'type': 'scatter',
        'name': '{}'.format('Transmit'),
    })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'bps',
            'tickformat': '~s',
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

    return JsonResponse(data)
