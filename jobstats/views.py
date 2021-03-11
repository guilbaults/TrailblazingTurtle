from django.shortcuts import render
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from .models import BelugaJobTable
import time
from django.conf import settings
from prometheus_api_client import PrometheusConnect
from prometheus_api_client.utils import parse_datetime
from datetime import datetime

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
            end = parse_datetime('now')
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


def index(request):
    context = {}
    return render(request, 'jobstats/index.html', context)

def user(request, user_id):
    context = {'user_id': user_id}
    week_ago = int(time.time()) - (3600 * 24 * 7)
    jobs = BelugaJobTable.objects.filter(id_user=user_id).order_by('-time_submit')[:100] # time_start__gt=week_ago
    context['jobs'] = jobs
    return render(request, 'jobstats/user.html', context)

def job(request, user_id, job_id):
    context = {'job_id': job_id}
    try:
        job = BelugaJobTable.objects.filter(id_user=user_id).filter(id_job=job_id).get()
    except:
        return HttpResponseNotFound('<h1>Job not found</h1>')
    context['job'] = job
    return render(request, 'jobstats/job.html', context)

def graph_cpu(request, user_id, job_id):
    prom = Prometheus(settings.PROMETHEUS['url'])
    try:
        job = BelugaJobTable.objects.filter(id_user=user_id).filter(id_job=job_id).get()
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

