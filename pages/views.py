from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from userportal.common import Prometheus, parse_start_end
from django.utils.translation import gettext as _
from datetime import datetime, timedelta
import statistics
import re

prom = Prometheus(settings.PROMETHEUS)


def index(request):
    context = {}
    context['cluster_intro'] = settings.CLUSTER_INTRO
    context['logins'] = settings.LOGINS.keys()
    context['dtns'] = settings.DTNS.keys()
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


def scheduler(request):
    context = {}
    return render(request, 'pages/scheduler.html', context)


def software(request):
    context = {}
    return render(request, 'pages/software.html', context)


@parse_start_end(minimum=prom.rate('lustre_exporter'))
def graph_lustre_mdt(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})

    query = 'sum(lustre:metadata:rate3m{{fs="{}", {}}}) by (operation) !=0'.format(fs, prom.get_filter())
    stats = prom.query_prometheus_multiple(
        query,
        request.start,
        end=request.end)

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


@parse_start_end(minimum=prom.rate('lustre_exporter'))
def graph_lustre_ost(request, fs):
    if fs not in settings.LUSTRE_FS_NAMES:
        return JsonResponse({'error': 'Unknown filesystem'})

    data = []
    for i in ['read', 'write']:
        query = 'lustre:{}_bytes:rate3m{{fs="{}", {}}}'.format(i, fs, prom.get_filter())
        stats = prom.query_prometheus_multiple(
            query,
            request.start,
            end=request.end,
            step=request.step)
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


@parse_start_end(minimum=prom.rate('node_exporter'))
def graph_login_cpu(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})

    core_count_query = 'count(node_cpu_seconds_total{{mode="system",{hostname_label}=~"{login}(:.*)?", {filter} }})'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        login=login,
        filter=prom.get_filter(),
    )
    core_count = max(prom.query_prometheus(
        core_count_query,
        request.start,
        end=request.end,
        step=request.step)[1])
    data = []
    query = 'sum by (mode)(rate(node_cpu_seconds_total{{mode=~"system|user|iowait",{hostname_label}=~"{login}(:.*)?", {filter} }}[{step}s]))'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        login=login,
        filter=prom.get_filter(),
        step=request.step,
    )
    stats = prom.query_prometheus_multiple(
        query,
        request.start,
        end=request.end,
        step=request.step)

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


@parse_start_end(minimum=prom.rate('node_exporter'))
def graph_login_memory(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})

    total_mem_query = 'node_memory_MemTotal_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }}'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        login=login,
        filter=prom.get_filter(),
    )
    total_mem = max(prom.query_prometheus(
        total_mem_query,
        request.start,
        end=request.end,
        step=request.step)[1])
    data = []
    query = 'node_memory_MemTotal_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }} - node_memory_MemFree_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }} - node_memory_Buffers_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }} - node_memory_Cached_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }} - node_memory_Slab_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }} - node_memory_PageTables_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }} - node_memory_SwapCached_bytes{{{hostname_label}=~"{login}(:.*)?", {filter} }}'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        login=login,
        filter=prom.get_filter(),
    )
    stats = prom.query_prometheus(
        query,
        request.start,
        end=request.end,
        step=request.step)
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


@parse_start_end(minimum=prom.rate('node_exporter'))
def graph_login_load(request, login):
    if login not in settings.LOGINS.keys():
        return JsonResponse({'error': 'Unknown login node'})
    data = []

    query = 'node_load1{{{hostname_label}=~"{login}(:.*)?", {filter} }}'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        login=login,
        filter=prom.get_filter(),
    )
    stats = prom.query_prometheus(
        query,
        request.start,
        end=request.end,
        step=request.step)
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


@parse_start_end(minimum=prom.rate('node_exporter'))
def graph_network(request, node, device):
    data = []
    query_rx = 'rate(node_network_receive_bytes_total{{{hostname_label}=~"{node}(:.*)?", device="{device}", {filter} }}[{step}s]) * 8'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter(),
        device=device,
        step=request.step,
    )
    stats_rx = prom.query_prometheus(
        query_rx,
        request.start,
        end=request.end,
        step=request.step)

    data.append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_rx[0])),
        'y': [-x for x in stats_rx[1]],
        'type': 'scatter',
        'fill': 'tozeroy',
        'name': '{}'.format('Receive'),
    })

    query_tx = 'rate(node_network_transmit_bytes_total{{{hostname_label}=~"{node}(:.*)?", device="{device}", {filter} }}[{step}s]) * 8'.format(
        hostname_label=settings.PROM_NODE_HOSTNAME_LABEL,
        node=node,
        filter=prom.get_filter(),
        device=device,
        step=request.step,
    )
    stats_tx = prom.query_prometheus(
        query_tx,
        request.start,
        end=request.end,
        step=request.step)

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


@parse_start_end(minimum=prom.rate('node_exporter'))
def graph_scheduler_cpu_gpu(request, res_type='cpu'):
    data = []
    if res_type == 'cpu':
        query_used = 'slurm_job:used_core:sum{{ {filter} }}'.format(
            filter=prom.get_filter(),
        )
    else:
        query_used = 'sum(slurm_job:used_gpu:sum{{ {filter} }})'.format(
            filter=prom.get_filter(),
        )

    stats_used = prom.query_prometheus(
        query_used,
        request.start,
        end=request.end,
        step=request.step)
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
    stats_alloc = prom.query_prometheus(
        query_alloc,
        request.start,
        end=request.end,
        step=request.step)
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
    stats_alloc = prom.query_prometheus(
        query_alloc,
        request.start,
        end=request.end,
        step=request.step)
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
        stats_non_idle = prom.query_prometheus(
            query_non_idle,
            request.start,
            end=request.end,
            step=request.step)
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
    stats_total = prom.query_prometheus(
        query_total,
        request.start,
        end=request.end,
        step=request.step)
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
    query_str = 'sum(deriv(slurm_job_process_usage_total{{ {} }}[2m]) > 0) by (exe)'
    return graph_software(query_str, settings.SOFTWARE_REGEX)


def graph_software_stack(request):
    query_str = 'sum(deriv(slurm_job_process_usage_total{{ {} }}[2m]) > 0) by (exe)'
    return graph_software(query_str, settings.SOFTWARE_STACK_REGEX, extract_path=True)


def graph_software_processes_cvmfs(request):
    query_str = 'sum(deriv(slurm_job_process_usage_total{{ exe=~"/cvmfs/.*", {} }}[2m]) > 0) by (exe)'
    return graph_software(query_str, settings.SOFTWARE_REGEX, unaccounted=False)


def graph_software_processes_not_cvmfs(request):
    query_str = 'sum(deriv(slurm_job_process_usage_total{{ exe!~"/cvmfs/.*", {} }}[2m]) > 0) by (exe)'
    return graph_software(query_str, settings.SOFTWARE_REGEX, unaccounted=False)


def graph_software_gpu(request):
    return graph_software(None, settings.SOFTWARE_REGEX, gpu=True, unaccounted=False)


def graph_software_cores_with_gpu(request):
    return graph_software(None, settings.SOFTWARE_REGEX, gpu=True, unaccounted=False, cores_with_gpu=True)


def graph_software(query_str, software_regexes, extract_path=False, unaccounted=True, gpu=False, cores_with_gpu=False):
    values_graph = []
    labels = []
    unidentified = 0
    accounted = 0
    software = {}

    # paths contain (path, used_cores, used_gpus)
    paths = []

    if gpu is True:
        query_gpu = 'count(slurm_job_utilization_gpu{{ {} }}) by (slurmjobid,gpu_type)'.format(prom.get_filter())
        stats_gpu = prom.query_prometheus_multiple(query_gpu, datetime.now() - timedelta(hours=6), step="5m")

        jobs = {}

        for line in stats_gpu:
            gpu_count = int(statistics.median(line['y']))
            jobs[int(line['metric']['slurmjobid'])] = gpu_count

        query_exe = 'sum(deriv(slurm_job_process_usage_total{{ slurmjobid=~"{jobids}", {filter} }}[1m]) > 0) by (exe,slurmjobid)'.format(
            jobids="|".join(map(str, jobs.keys())),
            filter=prom.get_filter(),
        )
        stats_exe = prom.query_prometheus_multiple(query_exe, datetime.now() - timedelta(hours=6), step="5m")

        for line in stats_exe:
            jobid = int(line['metric']['slurmjobid'])
            try:
                duration = line['x'][-1] - line['x'][0]
                if duration.total_seconds() < 5 * 60:
                    # job is too short to be accounted
                    continue
                ratio = duration.total_seconds() / (6 * 60 * 60)  # since we are querying 6 hours
                paths.append((line['metric']['exe'], statistics.mean(line['y']) * ratio, jobs[jobid] * ratio))
            except KeyError:
                continue
    else:
        query = query_str.format(prom.get_filter())
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours=6), step="5m")

        for line in stats:
            try:
                paths.append((line['metric']['exe'], statistics.median(line['y']), None))
            except KeyError:
                # Somehow the metric is missing the exe label
                continue

    for line in paths:
        bin = line[0]
        if cores_with_gpu is True:
            # show allocated cores with GPUs
            value = line[1]
        elif gpu is True:
            # show allocated GPUs
            value = line[2]
        else:
            value = line[1]
        basename = bin.split('/')[-1]
        for name, regex in software_regexes:
            if isinstance(regex, list):
                # not a regex but a list of binary names
                if basename in regex:
                    if name in software:
                        software[name] += value
                    else:
                        software[name] = value
                    accounted += value
                    break
            else:
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
        values_graph.append(software[key])

    if unidentified > 0:
        # Software that are not in the list of known regexes
        labels.append(_('Unidentified'))
        values_graph.append(unidentified)

    if unaccounted:
        query_used = 'slurm_job:used_core:sum{{ {} }}'.format(prom.get_filter())
        stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours=6), step="5m")
        used = statistics.median(stats_used[1])
        if used > accounted:
            labels.append(_('Unaccounted'))
            values_graph.append(used - accounted)

    data = {'data': [{
        'values': values_graph,
        'labels': labels,
        'type': 'pie',
        'texttemplate': '%{label}: %{value:.0f}',
    }]}

    data['layout'] = {
    }
    return JsonResponse(data)
