from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound, JsonResponse
from slurm.models import JobTable
from ccldap.models import LdapUser
from userportal.common import staff
from userportal.common import Prometheus
import time
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
import statistics


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))


@login_required
@staff
def account(request, account):
    context = {}
    return render(request, 'accountstats/account.html', context)

@login_required
@staff
def graph_cpu_used(request, account):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}
    query_used = 'sum(rate(slurm_job_core_usage_total{{account="{}"}}[5m])) by (user)/ 1000000000'.format(account)
    stats_used = prom.query_prometheus_multiple(query_used, datetime.now() - timedelta(hours=6), datetime.now())

    for line in stats_used:
        user = line['metric']['user']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': user
        })

    return JsonResponse(data)

def graph_cpu_allocated(request, account):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}
    query_alloc = 'count(slurm_job_core_usage_total{{account="{}"}}) by (user)/ 1000000000'.format(account)
    stats_alloc = prom.query_prometheus_multiple(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())

    for line in stats_alloc:
        user = line['metric']['user']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': user
        })

    return JsonResponse(data)

def graph_cpu_wasted(request, account):
    prom = Prometheus(settings.PROMETHEUS['url'])
    data = {'lines': []}
    query_alloc = 'count(slurm_job_core_usage_total{{account="{}"}}) by (user) - sum(rate(slurm_job_core_usage_total{{account="{}"}}[5m])) by (user)/ 1000000000'.format(account, account)
    stats_alloc = prom.query_prometheus_multiple(query_alloc, datetime.now() - timedelta(hours=6), datetime.now())

    for line in stats_alloc:
        user = line['metric']['user']
        x = list(map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'), line['x']))
        y = line['y']
        data['lines'].append({
            'x': x,
            'y': y,
            'type': 'scatter',
            'stackgroup': 'one',
            'name': user
        })

    return JsonResponse(data)

