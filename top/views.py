from django.shortcuts import render
from userportal.common import staff
from userportal.common import Prometheus
from slurm.models import JobTable
from ccldap.models import LdapUser
from django.conf import settings
from django.contrib.auth.decorators import login_required
import time


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
        stats_cpu_asked = line['value'][1]
        query_cpu_used = 'sum(rate(slurm_job_core_usage_total{{user="{}"}}[2m]) / 1000000000)'.format(user)
        stats_cpu_used = prom.query_last(query_cpu_used)

        query_mem_asked = 'sum(slurm_job_memory_limit{{user="{}"}})'.format(user)
        stats_mem_asked = prom.query_last(query_mem_asked)
        query_mem_max = 'sum(slurm_job_memory_max{{user="{}"}})'.format(user)
        stats_mem_max = prom.query_last(query_mem_max)

        mem_ratio = int(stats_mem_max[0]['value'][1]) / int(stats_mem_asked[0]['value'][1])
        if int(stats_mem_asked[0]['value'][1]) < 1 * 1024 * 1024 * 1024:
            # Asking under 1 GB, ignoring it
            mem_badge = None
        elif mem_ratio < 0.1:
            mem_badge = 'danger'
        elif mem_ratio < 0.5:
            mem_badge = 'warning'
        else:
            mem_badge = None

        if float(stats_cpu_used[0]['value'][1]) / float(stats_cpu_asked) < 0.9:
            cpu_badge = 'danger'
        else:
            cpu_badge = None

        cpu_users.append({
            'user': user,
            'cpu_asked': stats_cpu_asked,
            'cpu_used': stats_cpu_used[0]['value'][1],
            'mem_asked': stats_mem_asked[0]['value'][1],
            'mem_max': stats_mem_max[0]['value'][1],
            'mem_badge': mem_badge,
            'cpu_badge': cpu_badge,
        })

    context['cpu_users'] = cpu_users
    return render(request, 'top/compute.html', context)


@login_required
@staff
def largemem(request):
    context = {}
    prom = Prometheus(settings.PROMETHEUS['url'])

    hour_ago = int(time.time()) - (3600)
    week_ago = int(time.time()) - (3600 * 24 * 7)

    jobs_running = JobTable.objects.filter(
        time_start__lt=hour_ago,
        time_eligible__gt=week_ago,  # until time_start is indexed...
        partition__icontains='large',
        state=1).order_by('-time_submit')

    jobs = []
    for job in jobs_running:
        try:
            query_cpu_asked = 'count(slurm_job_core_usage_total{{slurmjobid="{}"}})'.format(job.id_job)
            stats_cpu_asked = prom.query_last(query_cpu_asked)
            query_cpu_used = 'sum(rate(slurm_job_core_usage_total{{slurmjobid="{}"}}[2m]) / 1000000000)'.format(job.id_job)
            stats_cpu_used = prom.query_last(query_cpu_used)

            query_mem_asked = 'sum(slurm_job_memory_limit{{slurmjobid="{}"}})'.format(job.id_job)
            stats_mem_asked = prom.query_last(query_mem_asked)
            query_mem_max = 'sum(slurm_job_memory_max{{slurmjobid="{}"}})'.format(job.id_job)
            stats_mem_max = prom.query_last(query_mem_max)

            if int(stats_mem_max[0]['value'][1]) < 4 * 1024 * 1024 * 1024:
                mem_badge = 'danger'
            elif int(stats_mem_max[0]['value'][1]) / int(stats_mem_asked[0]['value'][1]) < 0.5:
                mem_badge = 'warning'
            else:
                mem_badge = None

            if float(stats_cpu_used[0]['value'][1]) / float(stats_cpu_asked[0]['value'][1]) < 0.9:
                cpu_badge = 'danger'
            else:
                cpu_badge = None

            jobs.append({
                'user': LdapUser.objects.filter(uid=job.id_user).get().username,
                'job_id': job.id_job,
                'time_start_dt': job.time_start_dt,
                'cpu_asked': stats_cpu_asked[0]['value'][1],
                'cpu_used': stats_cpu_used[0]['value'][1],
                'mem_asked': stats_mem_asked[0]['value'][1],
                'mem_max': stats_mem_max[0]['value'][1],
                'mem_badge': mem_badge,
                'cpu_badge': cpu_badge,
            })
        except IndexError:
            jobs.append({
                'user': LdapUser.objects.filter(uid=job.id_user).get().username,
                'job_id': job.id_job,
                'mem_asked': 'error',
                'mem_max': 'error',
            })
        context['jobs'] = jobs
    return render(request, 'top/largemem.html', context)
