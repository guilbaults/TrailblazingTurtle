from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from slurm.models import JobTable
from ccldap.models import LdapUser
import time
from django.conf import settings
from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
import functools
import statistics

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


def user_or_staff(func):
   @functools.wraps(func)
   def wrapper(request, *args, **kwargs):
       if request.user.username == kwargs['username']:
           # own info
           return func(request, *args, **kwargs)
       elif LdapUser.objects.filter(username=request.user.username).get().employeeType == 'staff':
           # is staff
           return func(request, *args, **kwargs)
       else:
           return HttpResponseNotFound()
   return wrapper

@login_required
def index(request):
    return redirect('{}/'.format(request.user.username))

@login_required
@user_or_staff
def user(request, username):
    uid = LdapUser.objects.filter(username=username).get().uid
    context = {'username': username}
    pending_jobs = JobTable.objects.filter(id_user=uid, state=0).order_by('-time_submit')

    week_ago = int(time.time()) - (3600 * 24 * 7)  
    job_start = JobTable.objects.filter(id_user=uid, time_start__gt=week_ago).order_by('-time_submit')
    job_end = JobTable.objects.filter(id_user=uid, time_end__gt=week_ago).order_by('-time_submit')
    
    context['jobs'] = pending_jobs | job_start | job_end

    running_jobs = JobTable.objects.filter(id_user=uid, state=1).all()
    context['total_cores'] = 0
    context['total_mem'] = 0
    context['total_gpus'] = 0
    for job in running_jobs:
        info = job.parse_tres_req()
        context['total_cores'] += info['total_cores']
        context['total_mem'] += info['total_mem']
        context['total_gpus'] += job.gpu_count()

    prom = Prometheus(settings.PROMETHEUS['url'])
    now = datetime.now()
    delta = timedelta(hours = 1)
    try:
        query_cpu = 'sum(rate(slurm_job_core_usage_total{{user="{}"}}[2m]) / 1000000000)'.format(username)
        stats_cpu = prom.query_prometheus(query_cpu, now - delta, now)
        context['cpu_used'] = statistics.mean(stats_cpu[1])
    except ValueError:
        context['cpu_used'] = 'N/A'

    try:
        query_mem = 'sum(slurm_job_memory_max{{user="{}"}}/(1024*1024))'.format(username)
        stats_mem = prom.query_prometheus(query_mem, now - delta, now)
        context['mem_used'] = max(stats_mem[1])
    except ValueError:
        context['mem_used'] = 'N/A'

    try:
        query_gpu = 'sum(slurm_job_utilization_gpu{{user="{}"}})/100'.format(username)
        stats_gpu = prom.query_prometheus(query_gpu, now - delta, now)
        context['gpu_used'] = max(stats_gpu[1])
    except ValueError:
        context['gpu_used'] = 'N/A'

    return render(request, 'jobstats/user.html', context)

@login_required
@user_or_staff
def job(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    context = {'job_id': job_id}
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('<h1>Job not found</h1>')
    context['job'] = job
    context['tres_req'] = job.parse_tres_req()

    prom = Prometheus(settings.PROMETHEUS['url'])
    if job.time_start_dt() is None:
        return render(request, 'jobstats/job.html', context)

    try:
        query_cpu = 'sum(rate(slurm_job_core_usage_total{{exported_job="{}"}}[2m]) / 1000000000)'.format(job_id)
        stats_cpu = prom.query_prometheus(query_cpu, job.time_start_dt(), job.time_end_dt())
        context['cpu_used'] = statistics.mean(stats_cpu[1])
    except ValueError:
        context['cpu_used'] = 'N/A'

    try:
        query_mem = 'sum(slurm_job_memory_max{{exported_job="{}"}}/(1024*1024))'.format(job_id)
        stats_mem = prom.query_prometheus(query_mem, job.time_start_dt(), job.time_end_dt())
        context['mem_used'] = max(stats_mem[1])
    except ValueError:
        context['mem_used'] = 'N/A'

    if job.gpu_count() > 0:
        gpu_memory = {'v100': 16}
        gpu_full_power = {'v100': 300}
        gpu_idle_power = {'v100': 55}
        try:
            query_gpu_util = 'sum(slurm_job_utilization_gpu{{exported_job="{}"}})'.format(job_id)
            stats_gpu_util = prom.query_prometheus(query_gpu_util, job.time_start_dt(), job.time_end_dt())
            context['gpu_used'] = statistics.mean(stats_gpu_util[1])
        except ValueError:
            context['gpu_used'] = 'N/A'

        try:
            query_gpu_mem = 'sum(slurm_job_memory_usage_gpu{{exported_job="{}"}})/(1024*1024*1024)'.format(job_id)
            stats_gpu_mem = prom.query_prometheus(query_gpu_mem, job.time_start_dt(), job.time_end_dt())
            context['gpu_mem'] = max(stats_gpu_mem[1]) / gpu_memory[job.gpu_type()] * 100
        except ValueError:
            context['gpu_mem'] = 'N/A'

        try:
            query_gpu_power = 'sum(slurm_job_power_gpu{{exported_job="{}"}})/(1000)'.format(job_id)
            stats_gpu_power = prom.query_prometheus(query_gpu_power, job.time_start_dt(), job.time_end_dt())
            used_power = statistics.mean(stats_gpu_power[1]) - gpu_idle_power[job.gpu_type()]
            context['gpu_power'] = used_power / gpu_full_power[job.gpu_type()] * 100
        except ValueError:
            context['gpu_power'] = 'N/A'

    return render(request, 'jobstats/job.html', context)

@login_required
@user_or_staff
def graph_cpu(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
@user_or_staff
def graph_cpu_user(request, username):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = { 'lines': []}
    query_used = 'sum(rate(slurm_job_core_usage_total{{user="{}"}}[5m])) / 1000000000'.format(username)
    stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours = 6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
        'y': stats_used[1],
        'type': 'scatter',
        'name': 'Used'
    })

    query_alloc = 'sum(count(slurm_job_core_usage_total{{user="{}"}}))'.format(username)
    stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours = 6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
        'y': stats_alloc[1],
        'type': 'scatter',
        'name': 'Allocated'
    })

    data['layout'] = { 'yaxis':
        {
            'range': [ 0, max(stats_alloc[1])],
        }
    }
    return JsonResponse(data)

@login_required
@user_or_staff
def graph_mem_user(request, username):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = { 'lines': []}

    try:
        query_alloc = 'sum(slurm_job_memory_limit{{user="{}"}})/(1024*1024*1024)'.format(username)
        stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours = 6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
            'y': stats_alloc[1],
           'type': 'scatter',
           'name': 'Allocated'
        })
    except ValueError:
        pass

    try:
        query_max = 'sum(slurm_job_memory_max{{user="{}"}})/(1024*1024*1024)'.format(username)
        stats_max = prom.query_prometheus(query_max, datetime.now() - timedelta(hours = 6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_max[0])),
            'y': stats_max[1],
            'type': 'scatter',
            'name': 'Max used'
       })
    except ValueError:
        pass

    try:
        query_used = 'sum(slurm_job_memory_usage{{user="{}"}})/(1024*1024*1024)'.format(username)
        stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours = 6), datetime.now())
        data['lines'].append({
            'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
            'y': stats_used[1],
            'type': 'scatter',
            'name': 'Used'
        })
    except ValueError:
        pass

    data['layout'] = { 'yaxis': 
        {
            'ticksuffix': 'GiB',
            'range': [ 0, max(stats_alloc[1])],
        }
    }

    return JsonResponse(data)

@login_required
@user_or_staff
def graph_mem(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('Job not found')


    data = { 'lines': []}

    query_alloc = 'slurm_job_memory_limit{{exported_job="{}"}}/(1024*1024*1024)'.format(job_id)
    stats_alloc = prom.query_prometheus_multiple(query_alloc, job.time_start_dt(), job.time_end_dt())
    for line in stats_alloc:
        compute_name = line['metric']['instance'].split(':')[0]
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'name': 'Allocated {}'.format(compute_name)
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
@user_or_staff
def graph_lustre_mdt(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
@user_or_staff
def graph_lustre_mdt_user(request, username):
    prom = Prometheus(settings.PROMETHEUS['url'])

    query = 'sum(rate(lustre_job_stats_total{{component=~"mdt",user=~"{}"}}[5m])) by (operation, fs) !=0'.format(username)
    stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours = 6), datetime.now())
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
@user_or_staff
def graph_lustre_ost(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
@user_or_staff
def graph_lustre_ost_user(request, username):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = { 'lines': []}
    for i in ['read', 'write']:
        query = '(sum(rate(lustre_job_{}_bytes_total{{component=~"ost",user=~"{}",target=~".*-OST.*"}}[5m])) by (fs) !=0) / (1024*1024)'.format(i, username)
        stats = prom.query_prometheus_multiple(query, datetime.now() - timedelta(hours = 6), datetime.now())

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
@user_or_staff
def graph_gpu_utilization(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
            'ticksuffix': ' %',
            'range': [0, 100],
        }
    }
    return JsonResponse(data)

@login_required
@user_or_staff
def graph_gpu_utilization_user(request, username):
    prom = Prometheus(settings.PROMETHEUS['url'])

    data = { 'lines': []}

    query_alloc = 'count(slurm_job_utilization_gpu{{user="{}"}})'.format(username)
    stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours = 6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
        'y': stats_alloc[1],
        'type': 'scatter',
        'name': 'Allocated'
    })

    query_used = 'sum(slurm_job_utilization_gpu{{user="{}"}})/100'.format(username)
    stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours = 6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
        'y': stats_used[1],
        'type': 'scatter',
        'name': 'Used'
    })

    return JsonResponse(data)


@login_required
@user_or_staff
def graph_gpu_memory_utilization(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
            'ticksuffix': ' %',
            'range': [0, 100],
        }
    }
    return JsonResponse(data)

@login_required
@user_or_staff
def graph_gpu_memory(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
            'ticksuffix': ' GiB',
            'range': [0, 12],
        }
    }
    return JsonResponse(data)

@login_required
@user_or_staff
def graph_gpu_power(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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
            'ticksuffix': ' W',
            'range': [0, 300],
        }
    }
    return JsonResponse(data)

@login_required
@user_or_staff
def graph_gpu_power_user(request, username):
    prom = Prometheus(settings.PROMETHEUS['url'])

    data = { 'lines': []}

    # Fixme only support v100 at the moment
    query_alloc = 'count(slurm_job_power_gpu{{user="{}"}}) * 300'.format(username)
    stats_alloc = prom.query_prometheus(query_alloc, datetime.now() - timedelta(hours = 6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_alloc[0])),
        'y': stats_alloc[1],
        'type': 'scatter',
        'name': 'Allocated'
    })

    query_used = 'sum(slurm_job_power_gpu{{user="{}"}})/1000'.format(username)
    stats_used = prom.query_prometheus(query_used, datetime.now() - timedelta(hours = 6), datetime.now())
    data['lines'].append({
        'x': list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), stats_used[0])),
        'y': stats_used[1],
        'type': 'scatter',
        'name': 'Used'
    })

    data['layout'] = { 'yaxis':
        {
            'ticksuffix': ' W'
        }
    }

    return JsonResponse(data)

@login_required
@user_or_staff
def graph_gpu_pcie(request, username, job_id):
    uid = LdapUser.objects.filter(username=username).get().uid
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = JobTable.objects.filter(id_user=uid).filter(id_job=job_id).get()
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

