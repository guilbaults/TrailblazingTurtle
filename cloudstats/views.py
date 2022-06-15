from django.shortcuts import render
from django.http import JsonResponse
from userportal.common import openstackproject_or_staff, cloud_projects_by_user, request_to_username, staff, Prometheus, query_time
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from collections import Counter

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    context = {}
    context['projects'] = cloud_projects_by_user(request_to_username(request))

    if request.META['is_staff']:
        context['all_projects'] = []
        query_projects = 'count(libvirtd_domain_vcpu_time{{ {filter} }}) by (project_name)'.format(
            filter=prom.get_filter(),
        )
        for project in prom.query_last(query_projects):
            context['all_projects'].append({'name': project['metric']['project_name'], 'cores': int(project['value'][1])})

    return render(request, 'cloudstats/index.html', context)


@login_required
@openstackproject_or_staff
def project(request, project):
    context = {}
    query_instances = 'libvirtd_domain_domain_state{{project_name="{project}", {filter}}}'.format(
        project=project,
        filter=prom.get_filter())
    stats_instances = prom.query_prometheus_multiple(query_instances, datetime.now() - timedelta(days=7), datetime.now())

    context['instances'] = []
    for line in stats_instances:
        context['instances'].append(line['metric'])

    return render(request, 'cloudstats/project.html', context)


@login_required
@openstackproject_or_staff
def instance(request, project, uuid):
    context = {}

    return render(request, 'cloudstats/instance.html', context)


@login_required
@openstackproject_or_staff
def project_graph_cpu(request, project):
    data = {'lines': []}
    timing = query_time(request)
    query_used = 'sum(rate(libvirtd_domain_vcpu_time{{project_name="{project}", {filter}}}[1m])) by (uuid,instance_name) / 1000000000'.format(
        project=project,
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, timing[0], step=timing[1])

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
    query_running = 'sum(count(libvirtd_domain_vcpu_time{{project_name="{project}", {filter}}}))'.format(
        project=project,
        filter=prom.get_filter())
    stats_running = prom.query_prometheus_multiple(query_running, timing[0], step=timing[1])
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Running'),
        })

    data['layout'] = {
        'yaxis': {
            'title': _('Cores'),
        }
    }

    return JsonResponse(data)


@login_required
@staff
def projects_graph_cpu(request):
    data = {'lines': []}
    timing = query_time(request)
    query_used = 'sum(rate(libvirtd_domain_vcpu_time{{ {filter} }}[5m])) by (project_name) / 1000000000'.format(
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, timing[0], step=timing[1])
    for line in stats_used:
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': line['metric']['project_name']
        })

    query_running = 'sum(count(libvirtd_domain_vcpu_time{{ {filter} }})) by (project_name)'.format(
        filter=prom.get_filter())
    stats_running = prom.query_prometheus_multiple(query_running, timing[0], step=timing[1])
    for line in stats_running:
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': _('Running'),
        })

    data['layout'] = {
        'yaxis': {
            'title': _('Cores'),
        }
    }
    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def instance_graph_cpu(request, project, uuid):
    data = {'lines': []}
    timing = query_time(request)
    query_used = 'rate(libvirtd_domain_vcpu_time{{project_name="{project}", uuid="{uuid}", {filter}}}[1m]) / 1000000000'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, timing[0], step=timing[1])

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} {}'.format(_('Core'), line['metric']['vcpu'])
        })

    # Get the number of running cores
    query_running = 'sum(count(libvirtd_domain_vcpu_time{{project_name="{project}", uuid="{uuid}", {filter}}}))'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter())
    stats_running = prom.query_prometheus_multiple(query_running, timing[0], step=timing[1])
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Running'
        })

    data['layout'] = {
        'yaxis': {
            'title': _('Cores'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_memory(request, project):
    data = {'lines': []}
    timing = query_time(request)
    query_used = '(libvirtd_domain_balloon_current{{project_name="{project}", {filter}}} - libvirtd_domain_balloon_usable{{project_name="{project}", {filter}}})/1024/1024'.format(
        project=project,
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, timing[0], step=timing[1])

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
            'name': '{} {}'.format(_('Used'), name)
        })

    query_running = 'sum(libvirtd_domain_balloon_current{{project_name="{project}", {filter}}})/1024/1024'.format(
        project=project,
        filter=prom.get_filter())
    stats_running = prom.query_prometheus_multiple(query_running, timing[0], step=timing[1])
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Running'),
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'title': _('Memory'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def instance_graph_memory(request, project, uuid):
    data = {'lines': []}
    timing = query_time(request)
    query_used = '(libvirtd_domain_balloon_current{{project_name="{project}", uuid="{uuid}", {filter}}} - libvirtd_domain_balloon_usable{{project_name="{project}", uuid="{uuid}", {filter}}})/1024/1024'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, timing[0], step=timing[1])

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Used'),
        })

    query_running = 'sum(libvirtd_domain_balloon_current{{project_name="{project}", uuid="{uuid}", {filter}}})/1024/1024'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter())
    stats_running = prom.query_prometheus_multiple(query_running, timing[0], step=timing[1])
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Running'),
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'title': _('Memory'),
        }
    }

    return JsonResponse(data)


@login_required
@staff
def projects_graph_mem(request):
    data = {'lines': []}
    timing = query_time(request)
    query_used = 'sum((libvirtd_domain_balloon_current{{ {filter} }} - libvirtd_domain_balloon_usable{{ {filter} }})/1024/1024) by (project_name)'.format(
        filter=prom.get_filter())
    stats_used = prom.query_prometheus_multiple(query_used, timing[0], step=timing[1])
    for line in stats_used:
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': line['metric']['project_name']
        })

    query_running = 'sum((libvirtd_domain_balloon_current{{ {filter} }})/1024/1024)'.format(
        filter=prom.get_filter())
    stats_running = prom.query_prometheus_multiple(query_running, timing[0], step=timing[1])
    for line in stats_running:
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': _('Running'),
        })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'title': _('Memory'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_disk_bandwidth(request, project):
    data = {'lines': []}
    timing = query_time(request)

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_bytes{{project_name="{project}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            filter=prom.get_filter())
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, timing[0], step=timing[1])

        # Only show UUID if required
        instance_names = []
        for line in stats_bandwidth:
            instance_names.append(line['metric']['instance_name'])
        instance_counter = dict(Counter(instance_names))

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
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
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def instance_graph_disk_bandwidth(request, project, uuid):
    data = {'lines': []}
    timing = query_time(request)

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_bytes{{project_name="{project}", uuid="{uuid}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            uuid=uuid,
            filter=prom.get_filter())
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, timing[0], step=timing[1])

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': '{} {} {}'.format(direction, _('device'), line['metric']['device'])
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'MiB',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_disk_iops(request, project):
    data = {'lines': []}
    timing = query_time(request)

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_requests{{project_name="{project}", {filter}}}[1m])'.format(
            direction=direction,
            project=project,
            filter=prom.get_filter())
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, timing[0], step=timing[1])

        # Only show UUID if required
        instance_names = []
        for line in stats_bandwidth:
            instance_names.append(line['metric']['instance_name'])
        instance_counter = dict(Counter(instance_names))

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
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
            'title': _('IOPS'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def instance_graph_disk_iops(request, project, uuid):
    data = {'lines': []}
    timing = query_time(request)

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_requests{{project_name="{project}", uuid="{uuid}", {filter}}}[1m])'.format(
            direction=direction,
            project=project,
            uuid=uuid,
            filter=prom.get_filter())
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, timing[0], step=timing[1])

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {} {}'.format(direction, _('device'), line['metric']['device'])
            })

    data['layout'] = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def project_graph_network_bandwidth(request, project):
    data = {'lines': []}
    timing = query_time(request)

    for direction in ['rx', 'tx']:
        query_bandwidth = 'rate(libvirtd_domain_net_{direction}_bytes{{project_name="{project}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            filter=prom.get_filter())
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, timing[0], step=timing[1])

        # Only show UUID if required
        instance_names = []
        for line in stats_bandwidth:
            instance_names.append(line['metric']['instance_name'])
        instance_counter = dict(Counter(instance_names))

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'rx':
                y = line['y']
            else:
                y = [-x for x in line['y']]
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
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse(data)


@login_required
@openstackproject_or_staff
def instance_graph_network_bandwidth(request, project, uuid):
    data = {'lines': []}
    timing = query_time(request)

    for direction in ['rx', 'tx']:
        query_bandwidth = 'rate(libvirtd_domain_net_{direction}_bytes{{project_name="{project}", uuid="{uuid}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            uuid=uuid,
            filter=prom.get_filter())
        stats_bandwidth = prom.query_prometheus_multiple(query_bandwidth, timing[0], step=timing[1])

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'rx':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': direction
            })

    data['layout'] = {
        'yaxis': {
            'ticksuffix': 'MiB',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse(data)
