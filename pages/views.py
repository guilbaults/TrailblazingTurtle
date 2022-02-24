from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from userportal.common import Prometheus
from datetime import datetime, timedelta


def index(request):
    context = {}
    context['fs'] = settings.LUSTRE_FS_NAMES
    return render(request, 'pages/index.html', context)


def graph_lustre_mdt(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})

    prom = Prometheus(settings.PROMETHEUS)

    query = 'sum(rate(lustre_stats_total{{target=~"{}-.*", {}}}[5m])) by (operation) !=0'.format(fs, prom.get_filter())
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=24), step='5m')

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

    prom = Prometheus(settings.PROMETHEUS)

    data = {'lines': []}
    for i in ['read', 'write']:
        query = 'sum(rate(lustre_{}_bytes_total{{target=~"{}-.*", {} }}[5m]))'.format(i, fs, prom.get_filter())
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=24), step='5m')
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
