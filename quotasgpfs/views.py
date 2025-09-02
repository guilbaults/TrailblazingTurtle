from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.translation import gettext as _


from userportal.common import user_or_staff, parse_start_end, staff
from ccldap.models import LdapUser, LdapAllocation
from userportal.common import Prometheus

prom = Prometheus(settings.PROMETHEUS)
# - file system name and associated quota type: home/user, scratch/user, project/group
fs_home = settings.QUOTA_TYPES['home'][0]
fs_home_type = settings.QUOTA_TYPES['home'][1]
fs_scratch = settings.QUOTA_TYPES['scratch'][0]
fs_scratch_type = settings.QUOTA_TYPES['scratch'][1]
fs_project = settings.QUOTA_TYPES['project'][0]
fs_project_type = settings.QUOTA_TYPES['project'][1]
# - fs_key: 'fs' | 'fileset' - filesets are identified in prometheus as 'fileset', not 'fs'
fs_key="fs"
if settings.CLUSTER_NAME == "argo":
   fs_key="fileset"


@login_required
def index(request):
    return redirect("user/{}/".format(request.user.username.split("@")[0]))


@login_required
@user_or_staff
def user(request, username):
    context = {}
    quotas = []

    # get LdapUser
    user = LdapUser.objects.get(username=username)

    if not user:
        return HttpResponseNotFound()

    context["full_name"] = user.full_name
    context["username"] = user.username

    # User home quota
    quota = get_quota(fs_home_type, fs_home, str(user.uid), user.username, _("Home"))
    if quota:
        quotas.append(quota)

    # Get Group Project Quotas
    allocations = LdapAllocation.objects.filter(members=username, status="active").all()
    for allocation in allocations:
        quota = get_quota(
            fs_project_type,
            fs_project,
            str(allocation.gid),
            allocation.name,
            f"Project: {allocation.name}",
            show_breakdown=request.user.is_staff,
        )
        if quota:
            quotas.append(quota)

    # Get users personal group Quota

    # This is a special case, usage should be zero. Files end up in this quota if the user moves
    # files from their home directory to project, without changing the group to the project.

    quota = get_quota(
        fs_project_type,
        fs_project,
        str(user.group),
        user.username,
        f"Project: {user.username}",
        settings.POSIX_PERSONAL_GROUP_USAGE_NOTE,
    )
    if quota:
        if quota["usage_files"] > 0:
            quotas.append(quota)

    # Get User Scratch Quota
    quota = get_quota(fs_scratch_type, fs_scratch, str(user.uid), user.username, "Scratch")
    if quota:
        quotas.append(quota)

    context["quotas"] = quotas
    return render(request, "quotasgpfs/user.html", context)


def get_quota(
    quota_type, fs, name, allocation_name, friendly_name, note="", show_breakdown=False
):
    """
    Params:
    -------
    type: 'user' | 'group' | 'fileset'
    fs: 'home' | 'project' | 'scratch' - these may vary by site, e.g. depending on whether filesets are in use
    name: quota to query (on siku, uid/gid)
    allocation_name: cn of allocation
    friendly_name: Friendly name to show in portal
    """

    usage_bytes_metric = prom.query_last(
        'gpfs_%s_used_bytes{%s="%s", %s="%s"}' % (quota_type, fs_key, fs, quota_type, name)
    )
    quota_bytes_metric = prom.query_last(
        'gpfs_%s_quota_bytes{%s="%s", %s="%s"}' % (quota_type, fs_key, fs, quota_type, name)
    )

    usage_files_metric = prom.query_last(
        'gpfs_%s_used_files{%s="%s", %s="%s"}' % (quota_type, fs_key, fs, quota_type, name)
    )
    quota_files_metric = prom.query_last(
        'gpfs_%s_quota_files{%s="%s", %s="%s"}' % (quota_type, fs_key, fs, quota_type, name)
    )

    if not (usage_bytes_metric and quota_bytes_metric and usage_files_metric and quota_files_metric):
        return None

    usage_bytes = int(usage_bytes_metric[0]["value"][1])
    quota_bytes = int(quota_bytes_metric[0]["value"][1])

    usage_files = int(usage_files_metric[0]["value"][1])
    quota_files = int(quota_files_metric[0]["value"][1])

    return {
        "name": friendly_name,
        "fs": fs,
        "quota_name": name,
        "allocation_name": allocation_name,
        "usage_bytes": usage_bytes,
        "quota_bytes": quota_bytes,
        "percent_usage_bytes": min((usage_bytes / quota_bytes * 100), 100)
        if quota_bytes
        else 0,
        "usage_files": usage_files,
        "quota_files": quota_files,
        "percent_usage_files": min((usage_files / quota_files * 100), 100)
        if quota_files
        else 0,
        "note": note,
        "show_breakdown": show_breakdown,
    }


@login_required
@user_or_staff
@parse_start_end(minimum=prom.rate('slurm_exporter'))
def user_getgraph(request, username):
    fs = request.GET.get("fs")
    metric = request.GET.get("metric")
    name = request.GET.get("name")

    user = LdapUser.objects.get(username=username)

    # Validate Params
    if metric not in ["bytes", "files"]:
        return HttpResponseNotFound()

    if fs == fs_home or fs == fs_scratch:
        # Check the user is permitted to access this quota
        if str(user.uid) != name:
            return HttpResponseForbidden()
        quota_type = fs_home_type
    elif fs == fs_project:
        # Check the user is a member of the allocation
        if name != str(user.uid):
            alloc = LdapAllocation.objects.get(gid=name)
            if username not in alloc.members:
                return HttpResponseForbidden()
        quota_type = fs_project_type
    else:
        return HttpResponseNotFound()

    usage_query = 'gpfs_%s_used_%s{%s="%s", %s="%s"}' % (
        quota_type,
        metric,
        fs_key,
        fs,
        quota_type,
        name,
    )
    quota_query = 'gpfs_%s_quota_%s{%s="%s", %s="%s"}' % (
        quota_type,
        metric,
        fs_key,
        fs,
        quota_type,
        name,
    )

    usage = prom.query_prometheus(usage_query, request.start, None, step=request.step)
    quota = prom.query_prometheus(quota_query, request.start, None, step=request.step)

    return graph_prometheus_result(usage, quota, metric)


def graph_prometheus_result(stats, quota, metric):
    data = {"data": []}

    data["data"].append(
        {
            "x": list(map(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"), stats[0])),
            "y": stats[1],
            "type": "scatter",
            "fill": "tozeroy",
        }
    )

    data["data"].append(
        {
            "x": list(map(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"), stats[0])),
            "y": quota[1],
            "type": "scatter",
        }
    )

    data["layout"] = {
        "yaxis": {
            "title": "Usage",  # This needs to be translated
            "ticksuffix": "B" if metric == "bytes" else "",
            "tickformat": "~s",
            "range": [0, max(quota[1])],
        },
        "showlegend": False,
        "margin": {"l": 0, "r": 0, "b": 0, "t": 0, "pad": 0},
        "autosize": True,
        "useResizeHandler": True,
    }

    return JsonResponse(data)


@login_required
@staff
def project(request, project):
    context = {}

    # if any user is part of another allocation, the breakdown will be inaccurate,
    # this will warn the staff member.
    context["inaccurate"] = False

    # get ldap allocation
    allocation = LdapAllocation.objects.filter(name=project, status="active").get()

    # if no allocation is found, 404
    if not allocation:
        return HttpResponseNotFound()

    # get overall quota
    context["quota"] = get_quota(
        fs_project_type,
        fs_project,
        str(allocation.gid),
        allocation.name,
        f'{_("Project")}: {allocation.name}',
    )

    for memberuid in allocation.members:
        user = LdapUser.objects.filter(username=memberuid).get()

        # check if the user is a member of more than one allocation:
        if (len(LdapAllocation.objects.filter(members=user.username, status="active").all()) > 1):
            context["inaccurate"] = True

    return render(request, "quotasgpfs/project_breakdown.html", context)


@login_required
@staff
def project_getgraph(request, project):
    quotatype = request.GET.get("type")

    # validate params
    if quotatype not in ["bytes", "files"]:
        return HttpResponseNotFound()

    # get ldap allocation
    allocation = LdapAllocation.objects.filter(name=project, status="active").get()

    # if no allocation is found, 404
    if not allocation:
        return HttpResponseNotFound()

    pie = {"labels": [], "values": [], "type": "pie"}

    for memberuid in allocation.members:
        user = LdapUser.objects.filter(username=memberuid).get()

        quota = get_quota(fs_home_type, fs_project, str(user.uid), user.username, "")
        if quota is None:
            continue

        pie["labels"].append(user.username)
        pie["values"].append(quota[f"usage_{quotatype}"])

    data = {"data": []}

    data["data"].append(pie)

    data["layout"] = {
        "margin": {"l": 0, "r": 0, "b": 0, "t": 0, "pad": 0},
        "autosize": True,
        "useResizeHandler": True,
    }

    return JsonResponse(data)
