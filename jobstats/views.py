from django.shortcuts import render
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from .models import BelugaJobTable, LdapUser
import time
from django.conf import settings
from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime
from datetime import datetime
from django.contrib.auth.decorators import login_required

class Prometheus:
    def __init__(self, url):
        self.url = url
        self.prom = PrometheusConnect(url=url, disable_ssl=True)

    def query_prometheus(self, query, duration, step):
        values = self.query_prometheus_multiple(query, duration, step)
        if len(values) == 0:
            raise ValueError
        return (values[0]['x'], values[0]['y'])

    def query_prometheus_multiple(self, query, start, end=None):
        if end == None:
            end = datetime.now()
        q = self.prom.custom_query_range(
            query=query,
            start_time=start,
            end_time=end,
            step = '3m',
        )
        return_list = []
        for line in q:
            return_list.append({
                'metric': line['metric'],
                'x': [datetime.fromtimestamp(x[0]) for x in line['values']],
                'y': [float(x[1]) for x in line['values']]
            })
        return return_list

@login_required
def index(request):
    context = {}
    return render(request, 'jobstats/index.html', context)

@login_required
def user(request, username):
#    print(request.META['REMOTE_USER'])
#    print(request.user)
    uid = LdapUser.objects.filter(username=username).get().uid
    context = {'username': username}
    week_ago = int(time.time()) - (3600 * 24 * 7)
    jobs = BelugaJobTable.objects.filter(id_user=uid).order_by('-time_submit')[:100] # time_start__gt=week_ago
    context['jobs'] = jobs
    return render(request, 'jobstats/user.html', context)

@login_required
def job(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    context = {'job_id': job_id}
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('<h1>Job not found</h1>')
    context['job'] = job
    return render(request, 'jobstats/job.html', context)

@login_required
def graph_cpu(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    query = 'rate(slurm_job_core_usage_total{{exported_job="{}"}}[2m]) / 1000000000'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = { 'lines': []}
    for line in stats:
        core_num = int(line['metric']['core'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} core {}'.format(compute_name, core_num)
        })

    return JsonResponse(data)

@login_required
def graph_mem(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')


    data = { 'lines': []}

    query_req = 'slurm_job_memory_limit{{exported_job="{}"}}/(1024*1024*1024)'.format(job_id)
    stats_req = prom.query_prometheus_multiple(query_req, job.time_start_dt(), job.time_end_dt())
    for line in stats_req:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Requested {}'.format(compute_name)
        })

    query_max = 'slurm_job_memory_max{{exported_job="{}"}}/(1024*1024*1024)'.format(job_id)
    stats_max = prom.query_prometheus_multiple(query_max, job.time_start_dt(), job.time_end_dt())
    for line in stats_max:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Max used {}'.format(compute_name)
        })

    query_used = 'slurm_job_memory_usage{{exported_job="{}"}}/(1024*1024*1024)'.format(job_id)
    stats_used = prom.query_prometheus_multiple(query_used, job.time_start_dt(), job.time_end_dt())
    for line in stats_used:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Used {}'.format(compute_name)
        })

    data['layout'] = { 'yaxis': 
        {
            'ticksuffix': 'GiB'
        }
    }

    return JsonResponse(data)

@login_required
def graph_lustre_mdt(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    query = 'sum(rate(lustre_job_stats_total{{component=~"mdt",jobid=~"{}"}}[5m])) by (operation, fs) !=0'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = { 'lines': []}
    for line in stats:
        operation = line['metric']['operation']
        fs = line['metric']['fs']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} {}'.format(operation, fs)
        })

    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' IOPS'
        }
    }
    return JsonResponse(data)

@login_required
def graph_lustre_ost(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    data = { 'lines': []}
    for i in ['read', 'write']:
        query = '(sum(rate(lustre_job_{}_bytes_total{{component=~"ost",jobid=~"{}",target=~".*-OST.*"}}[5m])) by (fs) !=0) / (1024*1024)'.format(i, job_id)
        stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

        for line in stats:
            fs = line['metric']['fs']
            x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
            y = line['y']
            data['lines'].append({
                'x': x,
                'y': y,
                'type': 'scatter',
                'stackgroup': 'one',
                'name': '{} {}'.format(i, fs)
            })

    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' MiB/s'
        }
    }
    return JsonResponse(data)

@login_required
def graph_gpu_utilization(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_utilization_gpu{{exported_job="{}"}}'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = { 'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' %'
        }
    }
    return JsonResponse(data)

@login_required
def graph_gpu_memory_utilization(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_utilization_gpu_memory{{exported_job="{}"}}'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = { 'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' %'
        }
    }
    return JsonResponse(data)

@login_required
def graph_gpu_memory(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_memory_usage_gpu{{exported_job="{}"}} /(1024*1024*1024)'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = { 'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' GiB'
        }
    }
    return JsonResponse(data)

@login_required
def graph_gpu_power(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    query = 'slurm_job_power_gpu{{exported_job="{}"}}/1000'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    data = { 'lines': []}
    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} GPU {}'.format(compute_name, gpu_num)
        })
    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' W'
        }
    }
    return JsonResponse(data)

@login_required
def graph_gpu_pcie(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')

    data = { 'lines': []}
    # Not sure if this scale is correct, the API report both bytes and kb/s
    query = 'slurm_job_pcie_gpu{{exported_job="{}"}}/(1024*1024)'.format(job_id)
    stats = prom.query_prometheus_multiple(query, job.time_start_dt(), job.time_end_dt())

    for line in stats:
        gpu_num = int(line['metric']['gpu'])
        compute_name = line['metric']['instance'].split(':')[0]
        direction = line['metric']['direction']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': '{} GPU{} {}'.format(compute_name, gpu_num, direction)
        })

    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' MB/s'
        }
    }
    return JsonResponse(data)

