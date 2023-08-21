from django.shortcuts import render, redirect
from django.http import HttpResponseNotFound, HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.utils.translation import gettext as _


from userportal.common import user_or_staff, username_to_uid, query_time, staff
from ccldap.models import LdapUser, LdapCCAccount, LdapAllocation
from slurm.models import AcctTable
from userportal.common import Prometheus

prom = Prometheus(settings.PROMETHEUS)

@login_required
@staff
def index(request):
    return render(request, 'search/index.html')

@login_required
@staff
def query(request):
    querystring = request.GET.get('query')
    filtertype = request.GET.get('filtertype')
    results = []

    # Return early for empty string or only whitespace
    if len(querystring.split()) == 0:
        return JsonResponse({'query': querystring, 'results': results})



    # Query LDAP for users
    if settings.SEARCH_INCLUDE_USERS and (filtertype == "all" or filtertype == "users"):
        users = (LdapCCAccount.objects.filter(username__contains=querystring).all()) | (LdapCCAccount.objects.filter(full_name__contains=querystring).all())

        for user in users:

            filter = True
            if settings.SEARCH_USER_FILTER_CCSERVICEACCESS:
                for serviceaccess in user.ccServiceAccess:
                    if serviceaccess in settings.SEARCH_USER_FILTER_CCSERVICEACCESS:
                        filter = False
            else:
                filter = False

            if filter:
                continue

            results.append({
                'typetext': _('User'),
                'typefeathericon': 'user',
                'name': user.full_name,
                'username': user.username,
                'hyperlink': f'{settings.BASE_URL}secure/usersummary/{user.username}'
            })

    # Query SlurmDB for accounts
    if settings.SEARCH_INCLUDE_SLURM_ACCOUNTS  and (filtertype == "all" or filtertype == "slurm"):
        slurmaccounts = AcctTable.objects.filter(name__contains=querystring).all()
        for account in slurmaccounts:
            results.append({
                'typetext': _('Slurm Account'),
                'typefeathericon': 'users',
                'name': account.name,
                'username': account.description,
                'hyperlink': f'{settings.BASE_URL}secure/accountstats/{account.name}'
            })

    # Query GPFS Project Filesystem Quotas
    if ('quotasgpfs' in settings.INSTALLED_APPS) and settings.SEARCH_INCLUDE_GPFS_QUOTAS and (filtertype == "all" or filtertype == "quotas"):
        groups = LdapAllocation.objects.filter(name__contains=querystring).all()
        metrics = prom.query_last("gpfs_group_quota_bytes{fs=\"project\"}")
        gids_with_quotas = [int(metric['metric']['group']) for metric in metrics if metric['metric']['group'].isnumeric()]

        for group in groups:
            if group.gid not in gids_with_quotas:
                continue

            results.append({
                'typetext': _('Project Filesystem Quota'),
                'typefeathericon': 'hard-drive',
                'name': group.name,
                'username': '',
                'hyperlink': f'{settings.BASE_URL}secure/quotasgpfs/project/{group.name}'
            })

    if len(results) > settings.SEARCH_MAX_RETURNED:
        results = results[0:settings.SEARCH_MAX_RETURNED]
        results_truncated = True
    else:
        results_truncated = False

    resp = {
        'query': querystring,
        'results': results,
        'truncated': results_truncated
    }
    return JsonResponse(resp)