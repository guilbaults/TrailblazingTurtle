from django.shortcuts import render
from django.http import JsonResponse
from userportal.common import openstackproject_or_staff, cloud_projects_by_user, request_to_username, staff, Prometheus, parse_start_end
from userportal.common import anonymize as a
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from collections import Counter
import statistics

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    context = {}
    context['projects'] = cloud_projects_by_user(request_to_username(request))

    if request.user.is_staff:
        context['all_projects'] = []
        all_projects = {}

        query_count_cores = 'count(libvirtd_domain_vcpu_time{{ {filter} }}) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_avg_cores = prom.query_prometheus_multiple(query_count_cores, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_avg_cores:
            all_projects[line['metric']['project_name']] = {'cores': statistics.mean(line['y'])}

        query_used_cores = 'sum(rate(libvirtd_domain_vcpu_time{{ {filter} }}[1h])/1000/1000/1000) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_avg_used_cores = prom.query_prometheus_multiple(query_used_cores, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_avg_used_cores:
            all_projects[line['metric']['project_name']]['used_cores'] = statistics.mean(line['y'])

        query_memory = 'sum(libvirtd_domain_balloon_current{{ {filter} }}/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_memory = prom.query_prometheus_multiple(query_memory, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_memory:
            all_projects[line['metric']['project_name']]['memory'] = statistics.mean(line['y'])

        query_used_memory = 'sum((libvirtd_domain_balloon_current{{ {filter} }} - libvirtd_domain_balloon_usable{{ {filter} }})/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_used_memory = prom.query_prometheus_multiple(query_used_memory, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_used_memory:
            all_projects[line['metric']['project_name']]['used_memory'] = statistics.mean(line['y'])

        # infer the number of gpus from the instance_name
        query_gpus = 'count(libvirtd_domain_balloon_current{{ {filter} }}) by (project_name, instance_type)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_gpus = prom.query_prometheus_multiple(query_gpus, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_gpus:
            try:
                gpu_qty = settings.CLOUD_INSTANCE_TYPE[line['metric']['instance_type']]['gpu']
            except KeyError:
                gpu_qty = 0

            if 'gpu_qty' in all_projects[line['metric']['project_name']]:
                all_projects[line['metric']['project_name']]['gpu_qty'] =+ statistics.mean(line['y']) * gpu_qty
            else:
                all_projects[line['metric']['project_name']]['gpu_qty'] = statistics.mean(line['y']) * gpu_qty

        query_block_capacity = 'sum(libvirtd_domain_block_capacity{{ {filter} }}/1024/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_block_capacity = prom.query_prometheus_multiple(query_block_capacity, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_block_capacity:
            all_projects[line['metric']['project_name']]['block_capacity'] = statistics.mean(line['y'])

        context['total_projects'] = {'cores': 0, 'used_cores': 0, 'memory': 0, 'used_memory': 0, 'gpu_qty': 0, 'block_capacity': 0}
        for project in sorted(all_projects):
            context['all_projects'].append({
                'id': project,
                'name': project,
                'cores': all_projects[project]['cores'],
                'used_cores': all_projects[project]['used_cores'],
                'memory': all_projects[project]['memory'],
                'used_memory': all_projects[project]['used_memory'],
                'gpu_qty': all_projects[project]['gpu_qty'],
                'block_capacity': all_projects[project]['block_capacity'],
            })
            context['total_projects']['cores'] += all_projects[project]['cores']
            context['total_projects']['used_cores'] += all_projects[project]['used_cores']
            context['total_projects']['memory'] += all_projects[project]['memory']
            context['total_projects']['used_memory'] += all_projects[project]['used_memory']
            context['total_projects']['gpu_qty'] += all_projects[project]['gpu_qty']
            context['total_projects']['block_capacity'] += all_projects[project]['block_capacity']

        context['all_projects'].append({
            'id': 'total',
            'name': _('Total'),
            'cores': context['total_projects']['cores'],
            'used_cores': context['total_projects']['used_cores'],
            'memory': context['total_projects']['memory'],
            'used_memory': context['total_projects']['used_memory'],
            'gpu_qty': context['total_projects']['gpu_qty'],
            'block_capacity': context['total_projects']['block_capacity'],
        })

        # Grab the hypervisors hostnames
        query_hypervisors = 'libvirtd_info{{ {filter} }}'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_hypervisors = prom.query_prometheus_multiple(query_hypervisors, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        context['hypervisors'] = []
        for line in stats_hypervisors:
            context['hypervisors'].append(line['metric']['instance'].split(':')[0])

        # get the physical cores
        query_physical_cores = 'count(node_cpu_seconds_total{{ {filter}, mode="idle", instance=~"({instances}).*" }})'.format(
            filter=prom.get_filter('cloudstats'),
            instances='|'.join(context['hypervisors'])
        )
        stats_physical_cores = prom.query_last(query_physical_cores)
        context['physical_cores'] = stats_physical_cores[0]['value'][1]

        # get the physical memory
        query_physical_memory = 'sum(node_memory_MemTotal_bytes{{ {filter}, instance=~"({instances}).*" }})/1024/1024/1024'.format(
            filter=prom.get_filter('cloudstats'),
            instances='|'.join(context['hypervisors'])
        )
        stats_physical_memory = prom.query_last(query_physical_memory)
        context['physical_memory'] = stats_physical_memory[0]['value'][1]

    return render(request, 'cloudstats/index.html', context)


@login_required
@openstackproject_or_staff
def project(request, project):
    context = {}
    query_instances = 'libvirtd_domain_domain_state{{project_name="{project}", {filter}}}'.format(
        project=project,
        filter=prom.get_filter('cloudstats'))
    stats_instances = prom.query_prometheus_multiple(query_instances, datetime.now() - timedelta(days=7), datetime.now())

    context['instances'] = []
    for line in stats_instances:
        context['instances'].append(line['metric'])

    return render(request, 'cloudstats/project.html', context)


@login_required
@openstackproject_or_staff
def instance(request, project, uuid):
    context = {}
    query_instances = 'libvirtd_domain_domain_state{{project_name="{project}", uuid="{uuid}", {filter}}}'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter('cloudstats'))
    stats_instances = prom.query_prometheus_multiple(query_instances, datetime.now() - timedelta(days=7), datetime.now())
    context['instance_name'] = stats_instances[0]['metric']['instance_name']

    return render(request, 'cloudstats/instance.html', context)


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def project_graph_cpu(request, project):
    data = []
    query_used = 'sum(rate(libvirtd_domain_vcpu_time{{project_name="{project}", {filter}}}[1m])) by (uuid,instance_name) / 1000000000'.format(
        project=project,
        filter=prom.get_filter('cloudstats'))
    stats_used = prom.query_prometheus_multiple(
        query_used,
        request.start,
        end=request.end,
        step=request.step)

    # Only show UUID if required
    instance_names = []
    for line in stats_used:
        instance_names.append(line['metric']['instance_name'])
    instance_counter = dict(Counter(instance_names))

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if instance_counter[line['metric']['instance_name']] > 1:
            name = '{0} {1}'.format(a(line['metric']['instance_name']), line['metric']['uuid'])
        else:
            name = a(line['metric']['instance_name'])
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': name,
            'hovertemplate': '%{y:.1f}',
        })

    # Get the number of running cores
    query_running = 'sum(count(libvirtd_domain_vcpu_time{{project_name="{project}", {filter}}}))'.format(
        project=project,
        filter=prom.get_filter('cloudstats'))
    stats_running = prom.query_prometheus_multiple(
        query_running,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Running'),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'title': _('Cores'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def projects_graph_cpu(request):
    data = []
    query_used = 'sum(rate(libvirtd_domain_vcpu_time{{ {filter} }}[5m])) by (project_name) / 1000000000'.format(
        filter=prom.get_filter('cloudstats'))
    stats_used = prom.query_prometheus_multiple(
        query_used,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_used:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': a(line['metric']['project_name']),
            'hovertemplate': '%{y:.1f}',
        })

    query_running = 'sum(count(libvirtd_domain_vcpu_time{{ {filter} }})) by (project_name)'.format(
        filter=prom.get_filter('cloudstats'))
    stats_running = prom.query_prometheus_multiple(
        query_running,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_running:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': _('Running'),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'title': _('Cores'),
        }
    }
    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def instance_graph_cpu(request, project, uuid):
    data = []
    query_used = 'rate(libvirtd_domain_vcpu_time{{project_name="{project}", uuid="{uuid}", {filter}}}[1m]) / 1000000000'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter('cloudstats'))
    stats_used = prom.query_prometheus_multiple(
        query_used,
        request.start,
        end=request.end,
        step=request.step)

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} {}'.format(_('Core'), line['metric']['vcpu']),
            'hovertemplate': '%{y:.1f}',
        })

    # Get the number of running cores
    query_running = 'sum(count(libvirtd_domain_vcpu_time{{project_name="{project}", uuid="{uuid}", {filter}}}))'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter('cloudstats'))
    stats_running = prom.query_prometheus_multiple(
        query_running,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Running',
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'title': _('Cores'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def project_graph_memory(request, project):
    data = []
    query_used = '(libvirtd_domain_balloon_current{{project_name="{project}", {filter}}} - libvirtd_domain_balloon_usable{{project_name="{project}", {filter}}})/1024/1024'.format(
        project=project,
        filter=prom.get_filter('cloudstats'))
    stats_used = prom.query_prometheus_multiple(
        query_used,
        request.start,
        end=request.end,
        step=request.step)

    # Only show UUID if required
    instance_names = []
    for line in stats_used:
        instance_names.append(line['metric']['instance_name'])
    instance_counter = dict(Counter(instance_names))

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        if instance_counter[line['metric']['instance_name']] > 1:
            name = '{0} {1}'.format(a(line['metric']['instance_name']), line['metric']['uuid'])
        else:
            name = a(line['metric']['instance_name'])
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} {}'.format(_('Used'), name),
            'hovertemplate': '%{y:.1f}',
        })

    query_running = 'sum(libvirtd_domain_balloon_current{{project_name="{project}", {filter}}})/1024/1024'.format(
        project=project,
        filter=prom.get_filter('cloudstats'))
    stats_running = prom.query_prometheus_multiple(
        query_running,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Running'),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'title': _('Memory'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def instance_graph_memory(request, project, uuid):
    data = []
    query_used = '(libvirtd_domain_balloon_current{{project_name="{project}", uuid="{uuid}", {filter}}} - libvirtd_domain_balloon_usable{{project_name="{project}", uuid="{uuid}", {filter}}})/1024/1024'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter('cloudstats'))
    stats_used = prom.query_prometheus_multiple(
        query_used,
        request.start,
        end=request.end,
        step=request.step)

    for line in stats_used:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Used'),
            'hovertemplate': '%{y:.1f}',
        })

    query_running = 'sum(libvirtd_domain_balloon_current{{project_name="{project}", uuid="{uuid}", {filter}}})/1024/1024'.format(
        project=project,
        uuid=uuid,
        filter=prom.get_filter('cloudstats'))
    stats_running = prom.query_prometheus_multiple(
        query_running,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_running:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': _('Running'),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'title': _('Memory'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def projects_graph_mem(request):
    data = []
    query_used = 'sum((libvirtd_domain_balloon_current{{ {filter} }} - libvirtd_domain_balloon_usable{{ {filter} }})/1024/1024) by (project_name)'.format(
        filter=prom.get_filter('cloudstats'))
    stats_used = prom.query_prometheus_multiple(
        query_used,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_used:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'stackgroup': 'one',
            'name': a(line['metric']['project_name']),
            'hovertemplate': '%{y:.1f}',
        })

    query_running = 'sum((libvirtd_domain_balloon_current{{ {filter} }})/1024/1024)'.format(
        filter=prom.get_filter('cloudstats'))
    stats_running = prom.query_prometheus_multiple(
        query_running,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_running:
        data.append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x'])),
            'y': line['y'],
            'type': 'scatter',
            'name': _('Running'),
            'hovertemplate': '%{y:.1f}',
        })

    layout = {
        'yaxis': {
            'ticksuffix': 'GiB',
            'title': _('Memory'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def project_graph_disk_bandwidth(request, project):
    data = []

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_bytes{{project_name="{project}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            filter=prom.get_filter('cloudstats'))
        stats_bandwidth = prom.query_prometheus_multiple(
            query_bandwidth,
            request.start,
            end=request.end,
            step=request.step)

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
                name = '{0} {1}'.format(a(line['metric']['instance_name']), line['metric']['uuid'])
            else:
                name = a(line['metric']['instance_name'])
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, name),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': 'MiB',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def instance_graph_disk_bandwidth(request, project, uuid):
    data = []

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_bytes{{project_name="{project}", uuid="{uuid}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            uuid=uuid,
            filter=prom.get_filter('cloudstats'))
        stats_bandwidth = prom.query_prometheus_multiple(
            query_bandwidth,
            request.start,
            end=request.end,
            step=request.step)

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': '{} {} {}'.format(direction, _('device'), line['metric']['device']),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': 'MiB',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def project_graph_disk_iops(request, project):
    data = []

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_requests{{project_name="{project}", {filter}}}[1m])'.format(
            direction=direction,
            project=project,
            filter=prom.get_filter('cloudstats'))
        stats_bandwidth = prom.query_prometheus_multiple(
            query_bandwidth,
            request.start,
            end=request.end,
            step=request.step)

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
                name = '{0} {1}'.format(a(line['metric']['instance_name']), line['metric']['uuid'])
            else:
                name = a(line['metric']['instance_name'])
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, name),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def instance_graph_disk_iops(request, project, uuid):
    data = []

    for direction in ['read', 'write']:
        query_bandwidth = 'rate(libvirtd_domain_block_{direction}_requests{{project_name="{project}", uuid="{uuid}", {filter}}}[1m])'.format(
            direction=direction,
            project=project,
            uuid=uuid,
            filter=prom.get_filter('cloudstats'))
        stats_bandwidth = prom.query_prometheus_multiple(
            query_bandwidth,
            request.start,
            end=request.end,
            step=request.step)

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {} {}'.format(direction, _('device'), line['metric']['device']),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'title': _('IOPS'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def project_graph_network_bandwidth(request, project):
    data = []

    for direction in ['rx', 'tx']:
        query_bandwidth = 'rate(libvirtd_domain_net_{direction}_bytes{{project_name="{project}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            filter=prom.get_filter('cloudstats'))
        stats_bandwidth = prom.query_prometheus_multiple(
            query_bandwidth,
            request.start,
            end=request.end,
            step=request.step)

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
                name = '{0} {1}'.format(a(line['metric']['instance_name']), line['metric']['uuid'])
            else:
                name = a(line['metric']['instance_name'])
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {}'.format(direction, name),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': 'MiB',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@openstackproject_or_staff
@parse_start_end(minimum=prom.rate('libvirtd_exporter'))
def instance_graph_network_bandwidth(request, project, uuid):
    data = []

    for direction in ['rx', 'tx']:
        query_bandwidth = 'rate(libvirtd_domain_net_{direction}_bytes{{project_name="{project}", uuid="{uuid}", {filter}}}[1m])/1024/1024'.format(
            direction=direction,
            project=project,
            uuid=uuid,
            filter=prom.get_filter('cloudstats'))
        stats_bandwidth = prom.query_prometheus_multiple(
            query_bandwidth,
            request.start,
            end=request.end,
            step=request.step)

        for line in stats_bandwidth:
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if direction == 'rx':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'fill': 'tozeroy',
                'name': direction,
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': 'MiB',
            'title': _('Bandwidth'),
        }
    }

    return JsonResponse({'data': data, 'layout': layout})
