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
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
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
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data['lines'].append({
                'x': x,
                'y': y,
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
