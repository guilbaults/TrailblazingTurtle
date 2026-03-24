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

        query_quota_cores = 'openstack_quota_compute_cores{{ {filter} }}'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_quota_cores = prom.query_last(query_quota_cores)
        for line in stats_quota_cores:
            all_projects[line['metric']['project_name']] = {'quota_cores': float(line['value'][1])}

        query_count_cores = 'count(libvirtd_domain_vcpu_time{{ {filter} }}) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_running_cores = prom.query_last(query_count_cores)
        for line in stats_running_cores:
            all_projects.setdefault(line['metric']['project_name'], {})['running_cores'] = float(line['value'][1])

        query_used_cores = 'sum(rate(libvirtd_domain_vcpu_time{{ {filter} }}[1h])/1000/1000/1000) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_avg_used_cores = prom.query_prometheus_multiple(query_used_cores, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_avg_used_cores:
            all_projects[line['metric']['project_name']]['used_cores'] = statistics.mean(line['y'])

        query_quota_memory = 'openstack_quota_compute_ram{{ {filter} }}/1024'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_quota_memory = prom.query_last(query_quota_memory)
        for line in stats_quota_memory:
            all_projects[line['metric']['project_name']]['quota_memory'] = float(line['value'][1])

        query_running_memory = 'sum(libvirtd_domain_balloon_current{{ {filter} }}/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_running_memory = prom.query_last(query_running_memory)
        for line in stats_running_memory:
            all_projects[line['metric']['project_name']]['running_memory'] = float(line['value'][1])

        query_used_memory = 'sum((libvirtd_domain_balloon_current{{ {filter} }} - libvirtd_domain_balloon_usable{{ {filter} }})/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_used_memory = prom.query_prometheus_multiple(query_used_memory, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_used_memory:
            all_projects[line['metric']['project_name']]['used_memory'] = statistics.mean(line['y'])

        # infer the number of gpus from the instance_name
        query_running_gpus = 'count(libvirtd_domain_balloon_current{{ {filter} }}) by (project_name, instance_type)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_running_gpus = prom.query_last(query_running_gpus)
        for line in stats_running_gpus:
            try:
                gpu_qty = settings.CLOUD_INSTANCE_TYPE[line['metric']['instance_type']]['gpu']
            except KeyError:
                gpu_qty = 0

            if 'running_gpus' in all_projects[line['metric']['project_name']]:
                all_projects[line['metric']['project_name']]['running_gpus'] += float(line['value'][1]) * gpu_qty
            else:
                all_projects[line['metric']['project_name']]['running_gpus'] = float(line['value'][1]) * gpu_qty

        query_quota_block = 'openstack_quota_volume_gigabytes{{ {filter} }}'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_quota_block = prom.query_last(query_quota_block)
        for line in stats_quota_block:
            all_projects[line['metric']['project_name']]['quota_block'] = float(line['value'][1])

        query_running_block = 'sum(libvirtd_domain_block_capacity{{ {filter} }}/1024/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_running_block = prom.query_last(query_running_block)
        for line in stats_running_block:
            all_projects[line['metric']['project_name']]['running_block'] = float(line['value'][1])

        query_used_block = 'sum(libvirtd_domain_block_allocation{{ {filter} }}/1024/1024/1024) by (project_name)'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_avg_used_block = prom.query_prometheus_multiple(query_used_block, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_avg_used_block:
            all_projects[line['metric']['project_name']]['used_block'] = statistics.mean(line['y'])

        query_quota_object = 'openstack_quota_object_storage_x_account_meta_quota_bytes{{ {filter} }}/1024/1024/1024'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_quota_object = prom.query_last(query_quota_object)
        for line in stats_quota_object:
            all_projects[line['metric']['project_name']]['quota_object'] = float(line['value'][1])

        query_used_object = 'openstack_quota_object_storage_x_account_bytes_used{{ {filter} }}/1024/1024/1024'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_avg_used_object = prom.query_prometheus_multiple(query_used_object, datetime.now() - timedelta(days=31), datetime.now(), step='1d')
        for line in stats_avg_used_object:
            all_projects[line['metric']['project_name']]['used_object'] = statistics.mean(line['y'])

        query_quota_cephfs = 'openstack_quota_sharefs_gigabytes{{ {filter} }}'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_quota_cephfs = prom.query_last(query_quota_cephfs)
        for line in stats_quota_cephfs:
            all_projects[line['metric']['project_name']]['quota_cephfs'] = float(line['value'][1])

        query_running_cephfs = 'openstack_quota_sharefs_gigabytes_used{{ {filter} }}'.format(
            filter=prom.get_filter('cloudstats'),
        )
        stats_running_cephfs = prom.query_last(query_running_cephfs)
        for line in stats_running_cephfs:
            all_projects[line['metric']['project_name']]['running_cephfs'] = float(line['value'][1])

        context['total_projects'] = {'quota_cores': 0, 'running_cores': 0, 'used_cores': 0, 'quota_memory': 0, 'running_memory': 0, 'used_memory': 0, 'running_gpus': 0, 'quota_block': 0, 'running_block': 0, 'used_block': 0, 'quota_object': 0, 'used_object': 0, 'quota_cephfs': 0, 'running_cephfs': 0}
        for project in sorted(all_projects):
            context['all_projects'].append({
                'id': project,
                'name': project,
                'quota_cores': all_projects[project].get('quota_cores', 0),
                'running_cores': all_projects[project].get('running_cores', 0),
                'used_cores': all_projects[project].get('used_cores', 0),
                'quota_memory': all_projects[project].get('quota_memory', 0),
                'running_memory': all_projects[project].get('running_memory', 0),
                'used_memory': all_projects[project].get('used_memory', 0),
                'running_gpus': all_projects[project].get('running_gpus', 0),
                'quota_block': all_projects[project].get('quota_block', 0),
                'running_block': all_projects[project].get('running_block', 0),
                'used_block': all_projects[project].get('used_block', 0),
                'quota_object': all_projects[project].get('quota_object', 0),
                'used_object': all_projects[project].get('used_object', 0),
                'quota_cephfs': all_projects[project].get('quota_cephfs', 0),
                'running_cephfs': all_projects[project].get('running_cephfs', 0),
            })
            context['total_projects']['quota_cores'] += all_projects[project].get('quota_cores', 0)
            context['total_projects']['running_cores'] += all_projects[project].get('running_cores', 0)
            context['total_projects']['used_cores'] += all_projects[project].get('used_cores', 0)
            context['total_projects']['quota_memory'] += all_projects[project].get('quota_memory', 0)
            context['total_projects']['running_memory'] += all_projects[project].get('running_memory', 0)
            context['total_projects']['used_memory'] += all_projects[project].get('used_memory', 0)
            context['total_projects']['running_gpus'] += all_projects[project].get('running_gpus', 0)
            context['total_projects']['quota_block'] += all_projects[project].get('quota_block', 0)
            context['total_projects']['running_block'] += all_projects[project].get('running_block', 0)
            context['total_projects']['used_block'] += all_projects[project].get('used_block', 0)
            context['total_projects']['quota_object'] += all_projects[project].get('quota_object', 0)
            context['total_projects']['used_object'] += all_projects[project].get('used_object', 0)
            context['total_projects']['quota_cephfs'] += all_projects[project].get('quota_cephfs', 0)
            context['total_projects']['running_cephfs'] += all_projects[project].get('running_cephfs', 0)

        context['all_projects'].append({
            'id': 'total',
            'name': _('TOTAL'),
            'quota_cores': context['total_projects']['quota_cores'],
            'running_cores': context['total_projects']['running_cores'],
            'used_cores': context['total_projects']['used_cores'],
            'quota_memory': context['total_projects']['quota_memory'],
            'running_memory': context['total_projects']['running_memory'],
            'used_memory': context['total_projects']['used_memory'],
            'running_gpus': context['total_projects']['running_gpus'],
            'quota_block': context['total_projects']['quota_block'],
            'running_block': context['total_projects']['running_block'],
            'used_block': context['total_projects']['used_block'],
            'quota_object': context['total_projects']['quota_object'],
            'used_object': context['total_projects']['used_object'],
            'quota_cephfs': context['total_projects']['quota_cephfs'],
            'running_cephfs': context['total_projects']['running_cephfs'],
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
def resource_graphs(request):
    return render(request, 'cloudstats/resource_graphs.html')


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
