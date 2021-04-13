from django.shortcuts import render
from userportal.common import staff
from userportal.common import Prometheus
from django.conf import settings
from django.contrib.auth.decorators import login_required


@login_required
@staff
def index(request):
    return render(request, 'top/index.html')


@login_required
@staff
def compute(request):
    context = {}
    prom = Prometheus(settings.PROMETHEUS['url'])

    query_cpu = 'topk(100, count(slurm_job_core_usage_total) by (user))'
    stats_cpu = prom.query_last(query_cpu)
    cpu_users = []
    for line in stats_cpu:
        user = line['metric']['user']
        query_cpu_user = 'sum(rate(slurm_job_core_usage_total{{user="{}"}}[2m]) / 1000000000)'.format(user)
        stats_cpu_user = prom.query_last(query_cpu_user)

        query_mem_asked = 'sum(slurm_job_memory_limit{{user="{}"}})'.format(user)
        stats_mem_asked = prom.query_last(query_mem_asked)
        query_mem_max = 'sum(slurm_job_memory_max{{user="{}"}})'.format(user)
        stats_mem_max = prom.query_last(query_mem_max)

        cpu_users.append({
            'user': user,
            'core_asked': line['value'][1],
            'core_used': stats_cpu_user[0]['value'][1],
            'mem_asked': stats_mem_asked[0]['value'][1],
            'mem_max': stats_mem_max[0]['value'][1],
        })

    context['cpu_users'] = cpu_users
    return render(request, 'top/compute.html', context)
