from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from userportal.common import account_or_staff, Prometheus, parse_start_end
from userportal.common import compute_allocations_by_user, compute_allocations_by_slurm_account
from userportal.common import anonymize as a
from notes.models import Note


LONG_PERIOD = timedelta(days=60)
SHORT_PERIOD = timedelta(days=14)

prom = Prometheus(settings.PROMETHEUS)


@login_required
def index(request):
    context = {}
    username = request.user.get_username()
    context['compute_allocations'] = compute_allocations_by_user(username)
    return render(request, 'accountstats/index.html', context)


@login_required
@account_or_staff
def account(request, account):
    context = {}
    allocation = compute_allocations_by_slurm_account(account)
    if allocation is not None:
        if 'gpu' in allocation:
            context['gpu'] = True
            context['gpu_count'] = allocation['gpu']
        if 'cpu' in allocation:
            context['gpu'] = False
            context['cpu_count'] = allocation['cpu']
    context['account'] = account

    if request.user.is_staff:
        context['notes'] = Note.objects.filter(account=account).filter(deleted_at=None).order_by('-modified_at')

    return render(request, 'accountstats/account.html', context)


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_application(request, account):
    data = []
    query_alloc = 'slurm_job:process_usage:sum_account{{account="{}", {}}}'.format(account, prom.get_filter())
    stats_alloc = prom.query_prometheus_multiple(query_alloc, request.start, request.end, step=request.step)

    for line in stats_alloc:
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data.append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': line['metric']['bin'],
            'hovertemplate': '%{y:.1f}',
        })
    layout = {'showlegend': True}

    return JsonResponse({'data': data, 'layout': layout})


def graph(request, query, stacked=True, unit=None):
    data = []
    stats_alloc = prom.query_prometheus_multiple(
        query,
        request.start,
        end=request.end,
        step=request.step)
    for line in stats_alloc:
        user = line['metric']['user']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data_content = {
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': a(user),
            'hovertemplate': '%{y:.1f}',
        }
        if stacked:
            data_content['stackgroup'] = 'one'
        data.append(data_content)
    layout = {'showlegend': True}
    if unit is not None:
        layout['yaxis'] = {'ticksuffix': ' ' + unit}

    return JsonResponse({'data': data, 'layout': layout})


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_cpu_allocated(request, account):
    query_alloc = 'sum(slurm_job:allocated_core:count_user_account{{account="{}", {}}}) by (user)'.format(account, prom.get_filter())
    return graph(request, query_alloc, unit=_('cores'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_cpu_used(request, account):
    query_used = 'sum(slurm_job:used_core:sum_user_account{{account="{}", {}}}) by (user)'.format(account, prom.get_filter())
    return graph(request, query_used, unit=_('cores'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_cpu_wasted(request, account):
    query_alloc = 'clamp_min(sum(slurm_job:allocated_core:count_user_account{{account="{}", {}}}) by (user) - sum(slurm_job:used_core:sum_user_account{{account="{}", {}}}) by (user), 0)'.format(account, prom.get_filter(), account, prom.get_filter())
    return graph(request, query_alloc, stacked=False, unit=_('cores'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_mem_allocated(request, account):
    query_alloc = 'sum(slurm_job:allocated_memory:sum_user_account{{account="{}", {}}}) by (user) /(1024*1024*1024)'.format(account, prom.get_filter())
    return graph(request, query_alloc, unit=_('GiB'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_mem_used(request, account):
    query_used = 'sum(slurm_job:rss_memory:sum_user_account{{account="{}", {}}}) by (user) /(1024*1024*1024)'.format(account, prom.get_filter())
    return graph(request, query_used, unit=_('GiB'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_mem_wasted(request, account):
    query_alloc = 'clamp_min(sum(slurm_job:allocated_memory:sum_user_account{{account="{}", {}}}) by (user) - sum(slurm_job:rss_memory:sum_user_account{{account="{}", {}}}) by (user), 0) /(1024*1024*1024)'.format(account, prom.get_filter(), account, prom.get_filter())
    return graph(request, query_alloc, stacked=False, unit=_('GiB'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(hours=6), minimum=prom.rate('lustre_exporter'))
def graph_lustre_mdt(request, account):
    query = 'sum(rate(lustre_job_stats_total{{component=~"mdt",account=~"{}", {}}}[5m])) by (user, fs) !=0'.format(account, prom.get_filter())
    return graph(request, query, stacked=False, unit=_('IOPS'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(hours=6), minimum=prom.rate('lustre_exporter'))
def graph_lustre_ost(request, account):
    data = []
    for i in ['read', 'write']:
        query = '(sum(rate(lustre_job_{}_bytes_total{{component=~"ost",account=~"{}",target=~".*-OST.*", {}}}[5m])) by (user, fs)) / (1024*1024)'.format(i, account, prom.get_filter())
        stats = prom.query_prometheus_multiple(
            query,
            request.start,
            request.end,
            step=request.step)

        for line in stats:
            if 'fs' not in line['metric']:
                continue
            fs = line['metric']['fs']
            user = a(line['metric']['user'])
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            if i == 'read':
                y = line['y']
            else:
                y = [-x for x in line['y']]
            data.append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'name': '{} {} {}'.format(i, fs, user),
                'hovertemplate': '%{y:.1f}',
            })

    layout = {
        'yaxis': {
            'ticksuffix': ' MiB/s'
        },
        'showlegend': True
    }
    return JsonResponse({'data': data, 'layout': layout})


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_gpu_allocated(request, account):
    query = 'sum(slurm_job:allocated_gpu:count_user_account{{account="{}", {}}}) by (user)'.format(account, prom.get_filter())
    return graph(request, query, unit=_('GPUs'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_gpu_used(request, account):
    query = 'sum(slurm_job:used_gpu:sum_user_account{{account="{}", {}}}) by (user)'.format(account, prom.get_filter())
    return graph(request, query, unit=_('GPUs'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
def graph_gpu_wasted(request, account):
    query = 'sum(slurm_job:allocated_gpu:count_user_account{{account="{}", {}}}) by (user) - sum(slurm_job:used_gpu:sum_user_account{{account="{}", {}}}) by (user)'.format(account, prom.get_filter(), account, prom.get_filter())
    return graph(request, query, stacked=False, unit=_('GPUs'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
# kinda broken when using multiple GPUs
def graph_gpu_power_allocated(request, account):
    query = 'count(slurm_job_power_gpu{{account="{}", {}}}) by (user) * 300'.format(account, prom.get_filter())
    return graph(request, query, unit=_('W'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
# kinda broken when using multiple GPUs
def graph_gpu_power_used(request, account):
    query = 'sum(slurm_job_power_gpu{{account="{}", {}}}) by (user) / 1000'.format(account, prom.get_filter())
    return graph(request, query, unit=_('kW'))


@login_required
@account_or_staff
@parse_start_end(timedelta_start=timedelta(days=30), minimum=prom.rate('slurm-job-exporter'))
# kinda broken when using multiple GPUs
def graph_gpu_power_wasted(request, account):
    query = '(count(slurm_job_power_gpu{{account="{}", {}}}) by (user) * 300) - (sum(slurm_job_power_gpu{{account="{}", {}}}) by (user) / 1000)'.format(account, prom.get_filter(), account, prom.get_filter())
    return graph(request, query, stacked=False, unit=_('W'))


@login_required
@account_or_staff
def graph_cpu_priority(request, account):
    return graph_cpu_or_gpu_priority(request, account, 'cpu')


@login_required
@account_or_staff
def graph_gpu_priority(request, account):
    return graph_cpu_or_gpu_priority(request, account, 'gpu')


# auth done in functions above
@parse_start_end(timedelta_start=timedelta(days=90), minimum=prom.rate('slurm-job-exporter'))
def graph_cpu_or_gpu_priority(request, account, gpu_or_cpu):
    data = []
    if gpu_or_cpu == 'gpu':
        query_alloc = 'sum(slurm_job:allocated_gpu:count_user_account{{account="{}", {}}}) or vector(0)'.format(account, prom.get_filter())
    else:
        query_alloc = 'sum(slurm_job:allocated_core:count_user_account{{account="{}", {}}}) or vector(0)'.format(account, prom.get_filter())
    stats_alloc = prom.query_prometheus(query_alloc, request.start, request.end, step=request.step)

    x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0]))
    y = stats_alloc[1]
    allocated = {
        'x': x,
        'y': y,
        'type': 'scatter',
        'name': 'Allocated cores',
        'yaxis': 'y1',
    }
    if gpu_or_cpu == 'gpu':
        allocated['name'] = 'Allocated GPUs'
    else:
        allocated['name'] = 'Allocated cores'
    data.append(allocated)

    allocation = compute_allocations_by_slurm_account(account)
    if allocation is not None:
        if 'gpu' in allocation:
            alloc = allocation['gpu']
        if 'cpu' in allocation:
            alloc = allocation['cpu']
    else:
        alloc = 0
    if account.startswith('def-') is False:
        data.append({
            'x': x,
            'y': [alloc] * len(x),
            'type': 'scatter',
            'name': 'Allocation',
            'yaxis': 'y1',
            'hovertemplate': '%{y:.1f}',
        })

    if gpu_or_cpu == 'gpu':
        query_used = 'sum(slurm_job:used_gpu:sum_user_account{{account="{}", {}}}) or vector(0)'.format(account, prom.get_filter())
    else:
        query_used = 'sum(slurm_job:used_core:sum_user_account{{account="{}", {}}}) or vector(0)'.format(account, prom.get_filter())
    stats_used = prom.query_prometheus(query_used, request.start, request.end, step=request.step)

    x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0]))
    y = stats_used[1]
    used = {
        'x': x,
        'y': y,
        'type': 'scatter',
        'yaxis': 'y1',
    }
    if gpu_or_cpu == 'gpu':
        used['name'] = 'Used GPUs'
    else:
        used['name'] = 'Used cores'
    data.append(used)

    query_levelfs = 'slurm_account_levelfs{{account="{}", {}}}'.format(account, prom.get_filter())
    stats_levelfs = prom.query_prometheus(query_levelfs, request.start, request.end, step=request.step)

    x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_levelfs[0]))
    y = stats_levelfs[1]
    data.append({
        'x': x,
        'y': y,
        'type': 'scatter',
        'name': 'Priority',
        'yaxis': 'y2',
        'hovertemplate': '%{y:.1f}',
    })

    if gpu_or_cpu == 'gpu':
        title = 'GPUs'
    else:
        title = 'Cores'
    layout = {
        'yaxis': {
            'title': title,
            'range': [0, max(stats_alloc[1])],
        },
        'yaxis2': {
            'title': 'Priority',
            'overlaying': 'y',
            'side': 'right',
            'range': [0, max(stats_levelfs[1])],
        },
        'showlegend': True,
    }

    return JsonResponse({'data': data, 'layout': layout})
