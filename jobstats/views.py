from django.shortcuts import render
from django.http import HttpResponse
from .models import BelugaJobTable
import time

def index(request):
    context = {}
    week_ago = int(time.time()) - (3600 * 24 * 7)
    jobs = BelugaJobTable.objects.filter(id_user="3015160")[0:5] # time_start__gt=week_ago
    context['jobs'] = jobs
    return render(request, 'jobstats/index.html', context)

def job(request, job_id):
    context = {'job_id': job_id}
    return render(request, 'jobstats/job.html', context)
