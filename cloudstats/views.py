from django.shortcuts import render
from django.http import JsonResponse
from userportal.common import openstackproject_or_staff
from userportal.common import Prometheus
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from collections import Counter


@login_required
@openstackproject_or_staff
def project(request, project):
    context = {}
    return render(request, 'cloudstats/project.html', context)


@login_required
@openstackproject_or_staff
def project_graph_cpu(request, project):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}
    query_used = 'sum(rate(libvirtd_domain_vcpu_time{{project_name="{}"}}[1m])) by (uuid,instance_name) / 1000000000'.format(project)
    stats_used = prom.query_prometheus_multiple(query_used, datetime.now() - timedelta(days=7), datetime.now())

    # Only show UUID if required
    instance_names = []
    for line in stats_used:
        instance_names.append(line['metric']['instance_name'])
    instance_counter = dict(Counter(instance_names))

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if instance_counter[line['metric']['instance_name']] > 1:
            name = '{0} {1}'.format(line['metric']['instance_name'], line['metric']['uuid'])
        else:
            name = line['metric']['instance_name']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': name
        })

    # Get the number of running cores
    query_running = 'sum(count(libvirtd_domain_vcpu_time{{project_name="{}"}}))'.format(project)
    stats_running = prom.query_prometheus_multiple(query_running, datetime.now() - timedelta(days=7), datetime.now())
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Running'
        })

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_memory(request, project):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}
    query_used = '(libvirtd_domain_balloon_current{{project_name="{}"}} - libvirtd_domain_balloon_usable{{project_name="{}"}})/1024/1024'.format(project, project)
    stats_used = prom.query_prometheus_multiple(query_used, datetime.now() - timedelta(days=7), datetime.now())

    # Only show UUID if required
    instance_names = []
    for line in stats_used:
        instance_names.append(line['metric']['instance_name'])
    instance_counter = dict(Counter(instance_names))

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if instance_counter[line['metric']['instance_name']] > 1:
            name = '{0} {1}'.format(line['metric']['instance_name'], line['metric']['uuid'])
        else:
            name = line['metric']['instance_name']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Used {}'.format(name)
        })

    query_size = 'libvirtd_domain_balloon_current{{project_name="{}"}}/1024/1024'.format(project)
    stats_size = prom.query_prometheus_multiple(query_size, datetime.now() - timedelta(days=7), datetime.now())

    # Only show UUID if required
    instance_names = []
    for line in stats_size:
        instance_names.append(line['metric']['instance_name'])
    instance_counter = dict(Counter(instance_names))

    for line in stats_size:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if instance_counter[line['metric']['instance_name']] > 1:
            name = '{0} {1}'.format(line['metric']['instance_name'], line['metric']['uuid'])
        else:
            name = line['metric']['instance_name']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Size {}'.format(name)
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'GiB',
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_disk_bandwidth(request, project):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{}_bytes{{project_name="{}"}}[1m])/1024/1024'.format(direction, project)
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, datetime.now() - timedelta(days=7), datetime.now())

        # Only show UUID if required
        instance_names = []
        for line in stats_bandwidth:
            instance_names.append(line['metric']['instance_name'])
        instance_counter = dict(Counter(instance_names))

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            if instance_counter[line['metric']['instance_name']] > 1:
                name = '{0} {1}'.format(line['metric']['instance_name'], line['metric']['uuid'])
            else:
                name = line['metric']['instance_name']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, name)
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'MiB',
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_disk_iops(request, project):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{}_requests{{project_name="{}"}}[1m])'.format(direction, project)
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, datetime.now() - timedelta(days=7), datetime.now())

        # Only show UUID if required
        instance_names = []
        for line in stats_bandwidth:
            instance_names.append(line['metric']['instance_name'])
        instance_counter = dict(Counter(instance_names))

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            if instance_counter[line['metric']['instance_name']] > 1:
                name = '{0} {1}'.format(line['metric']['instance_name'], line['metric']['uuid'])
            else:
                name = line['metric']['instance_name']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, name)
            })

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_network_bandwidth(request, project):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}

    for direction in ['rx', 'tx']:
        query_bandwidth = 'rate(libvirtd_domain_net_{}_bytes{{project_name="{}"}}[1m])/1024/1024'.format(direction, project)
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, datetime.now() - timedelta(days=7), datetime.now())

        # Only show UUID if required
        instance_names = []
        for line in stats_bandwidth:
            instance_names.append(line['metric']['instance_name'])
        instance_counter = dict(Counter(instance_names))

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            if instance_counter[line['metric']['instance_name']] > 1:
                name = '{0} {1}'.format(line['metric']['instance_name'], line['metric']['uuid'])
            else:
                name = line['metric']['instance_name']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, name)
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'MiB',
        }
    }

    return JsonResponse(data)
