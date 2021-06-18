from django.shortcuts import render, redirect
from userportal.common import user_or_staff
from django.contrib.auth.decorators import login_required
from ccldap.common import storage_allocations
from .common import project_user_quota, project_used
from .common import nearline_user_quota, nearline_used


@login_required
def index(request):
    return redirect('{}/'.format(request.user.username.split('@')[0]))


@login_required
@user_or_staff
def user(request, username):
    context = {}
    context['projects'] = []
    context['nearlines'] = []
    alloc_projects, alloc_nearlines = storage_allocations(username)

    for alloc in alloc_projects:
        project = {}
        project['name'] = alloc['name']
        project['users'] = project_user_quota(alloc['name'])
        project['used'] = project_used(alloc['name'], alloc)
        context['projects'].append(project)

    for alloc in alloc_nearlines:
        nearline = {}
        nearline['name'] = alloc['name']
        nearline['users'] = nearline_user_quota(alloc['name'])
        nearline['used'] = nearline_used(alloc['name'], alloc)
        context['nearlines'].append(nearline)

    return render(request, 'quotas/index.html', context)
