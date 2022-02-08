from django.shortcuts import render, redirect
from ccldap.models import LdapUser
from userportal.common import user_or_staff
from django.contrib.auth.decorators import login_required
from slurm.models import JobTable


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))


@login_required
@user_or_staff
def user(request, username):
    uid = LdapUser.objects.filter(username=username).get().uid
    context = {'username': username}
    pending_jobs = JobTable.objects.filter(
        id_user=uid, state=0).order_by('-time_submit')

    job_start = JobTable.objects.filter(
        id_user=uid).order_by('-time_submit')
    job_end = JobTable.objects.filter(
        id_user=uid).order_by('-time_submit')

    context['jobs'] = (pending_jobs | job_start | job_end)[:10]

    running_jobs = JobTable.objects.filter(id_user=uid, state=1).all()
    context['total_cores'] = 0
    context['total_mem'] = 0
    context['total_gpus'] = 0
    for job in running_jobs:
        info = job.parse_tres_req()
        context['total_cores'] += info['total_cores']
        context['total_mem'] += (info['total_mem'] * 1024 * 1024)
        context['total_gpus'] += job.gpu_count()

    return render(request, 'usersummary/user.html', context)
